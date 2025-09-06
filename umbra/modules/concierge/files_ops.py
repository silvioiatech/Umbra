"""
File Operations for Concierge

Provides secure file transfer capabilities with:
- Export/import with automatic chunking (≤100MB parts)
- SHA-256 integrity verification
- Atomic writes with temp→fsync→move
- Directory and archive support
- Progress tracking for large transfers
"""
import os
import hashlib
import shutil
import tempfile
import tarfile
import zipfile
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, BinaryIO
from dataclasses import dataclass

@dataclass
class FileChunk:
    """File chunk information."""
    chunk_id: int
    offset: int
    size: int
    sha256: str
    data: bytes

@dataclass
class FileManifest:
    """File transfer manifest with integrity information."""
    operation_id: str
    file_path: str
    total_size: int
    chunk_count: int
    chunk_size: int
    chunks: List[Dict[str, Any]]
    file_sha256: str
    created_at: float
    compression: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class TransferResult:
    """File transfer operation result."""
    success: bool
    operation_id: str
    file_path: str
    total_size: int
    chunks_transferred: int
    transfer_time: float
    integrity_verified: bool
    error: Optional[str] = None

class FileOps:
    """Secure file operations with chunking and integrity verification."""
    
    def __init__(self, config):
        self.config = config
        
        # Configuration
        self.max_file_size = getattr(config, 'FILE_LIMIT_MB', 100) * 1024 * 1024  # 100MB default
        self.split_threshold = getattr(config, 'SPLIT_ABOVE_MB', 100) * 1024 * 1024
        self.chunk_size = getattr(config, 'CHUNK_MB', 8) * 1024 * 1024  # 8MB chunks
        self.integrity_algorithm = getattr(config, 'INTEGRITY', 'sha256')
        
        # Safe directories for file operations
        self.safe_directories = [
            '/tmp',
            '/var/tmp',
            '/home',
            '/opt',
            '/srv',
            '/var/www',
            '/var/log'
        ]
        
        # Temp directory for staging
        self.temp_dir = Path(tempfile.gettempdir()) / 'umbra_file_ops'
        self.temp_dir.mkdir(exist_ok=True)
    
    def _generate_operation_id(self) -> str:
        """Generate unique operation ID."""
        return hashlib.sha256(f"{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()[:16]
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if path is in safe directories."""
        abs_path = os.path.abspath(path)
        
        # Check against safe directories
        for safe_dir in self.safe_directories:
            if abs_path.startswith(safe_dir):
                return True
        
        return False
    
    def _calculate_file_hash(self, file_path: str, algorithm: str = 'sha256') -> str:
        """Calculate file hash using specified algorithm."""
        hash_func = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    def _calculate_chunk_hash(self, data: bytes, algorithm: str = 'sha256') -> str:
        """Calculate hash for data chunk."""
        hash_func = hashlib.new(algorithm)
        hash_func.update(data)
        return hash_func.hexdigest()
    
    def file_send(
        self,
        path: str,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_part_mb: int = 100,
        compress: bool = True
    ) -> Tuple[bool, FileManifest, str]:
        """
        Export file or directory with chunking and integrity.
        
        Args:
            path: File or directory path to export
            include_patterns: Patterns to include (glob style)
            exclude_patterns: Patterns to exclude (glob style)
            max_part_mb: Maximum part size in MB
            compress: Whether to compress archive
        
        Returns:
            Tuple of (success, manifest, error_message)
        """
        try:
            # Validate path
            if not self._is_safe_path(path):
                return False, None, f"Path not in safe directories: {path}"
            
            if not os.path.exists(path):
                return False, None, f"Path does not exist: {path}"
            
            # Generate operation ID
            operation_id = self._generate_operation_id()
            
            # Determine if we need to create archive
            source_path = path
            cleanup_archive = False
            
            if os.path.isdir(path):
                # Create archive for directories
                archive_path = self.temp_dir / f"{operation_id}.tar.gz"
                
                with tarfile.open(archive_path, 'w:gz' if compress else 'w') as tar:
                    tar.add(path, arcname=os.path.basename(path))
                
                source_path = str(archive_path)
                cleanup_archive = True
            
            # Check file size
            file_size = os.path.getsize(source_path)
            max_size = max_part_mb * 1024 * 1024
            
            if file_size > max_size:
                if cleanup_archive:
                    os.unlink(source_path)
                return False, None, f"File too large: {file_size} bytes (max: {max_size})"
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(source_path, self.integrity_algorithm)
            
            # Create chunks
            chunks = []
            chunk_id = 0
            
            with open(source_path, 'rb') as f:
                while True:
                    offset = f.tell()
                    chunk_data = f.read(self.chunk_size)
                    
                    if not chunk_data:
                        break
                    
                    chunk_hash = self._calculate_chunk_hash(chunk_data, self.integrity_algorithm)
                    
                    chunk_info = {
                        'chunk_id': chunk_id,
                        'offset': offset,
                        'size': len(chunk_data),
                        'sha256': chunk_hash
                    }
                    
                    chunks.append(chunk_info)
                    
                    # Save chunk to temp file
                    chunk_path = self.temp_dir / f"{operation_id}_chunk_{chunk_id}"
                    with open(chunk_path, 'wb') as chunk_file:
                        chunk_file.write(chunk_data)
                    
                    chunk_id += 1
            
            # Create manifest
            manifest = FileManifest(
                operation_id=operation_id,
                file_path=path,
                total_size=file_size,
                chunk_count=len(chunks),
                chunk_size=self.chunk_size,
                chunks=chunks,
                file_sha256=file_hash,
                created_at=time.time(),
                compression='gzip' if compress and cleanup_archive else None,
                metadata={
                    'original_path': path,
                    'is_directory': os.path.isdir(path),
                    'include_patterns': include_patterns,
                    'exclude_patterns': exclude_patterns
                }
            )
            
            # Save manifest
            manifest_path = self.temp_dir / f"{operation_id}_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest.__dict__, f, indent=2)
            
            # Cleanup temporary archive if created
            if cleanup_archive:
                os.unlink(source_path)
            
            return True, manifest, ""
            
        except Exception as e:
            return False, None, f"Export failed: {str(e)}"
    
    def file_receive(
        self,
        manifest: FileManifest,
        destination: str,
        overwrite: bool = False,
        mode: Optional[int] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None
    ) -> Tuple[bool, TransferResult, str]:
        """
        Import file with atomic writes and integrity verification.
        
        Args:
            manifest: File manifest from export operation
            destination: Destination path
            overwrite: Whether to overwrite existing files
            mode: File permissions (octal)
            owner: File owner (username)
            group: File group (groupname)
        
        Returns:
            Tuple of (success, transfer_result, error_message)
        """
        start_time = time.time()
        
        try:
            # Validate destination
            if not self._is_safe_path(destination):
                return False, None, f"Destination not in safe directories: {destination}"
            
            # Check if destination exists
            if os.path.exists(destination) and not overwrite:
                return False, None, f"Destination exists and overwrite=False: {destination}"
            
            # Create destination directory if needed
            dest_dir = os.path.dirname(destination)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Verify all chunks are available
            missing_chunks = []
            for chunk_info in manifest.chunks:
                chunk_path = self.temp_dir / f"{manifest.operation_id}_chunk_{chunk_info['chunk_id']}"
                if not chunk_path.exists():
                    missing_chunks.append(chunk_info['chunk_id'])
            
            if missing_chunks:
                return False, None, f"Missing chunks: {missing_chunks}"
            
            # Create temporary file for atomic write
            temp_dest = f"{destination}.tmp.{manifest.operation_id}"
            
            chunks_transferred = 0
            
            # Reassemble file from chunks
            with open(temp_dest, 'wb') as output_file:
                for chunk_info in manifest.chunks:
                    chunk_path = self.temp_dir / f"{manifest.operation_id}_chunk_{chunk_info['chunk_id']}"
                    
                    # Read and verify chunk
                    with open(chunk_path, 'rb') as chunk_file:
                        chunk_data = chunk_file.read()
                    
                    # Verify chunk integrity
                    chunk_hash = self._calculate_chunk_hash(chunk_data, self.integrity_algorithm)
                    if chunk_hash != chunk_info['sha256']:
                        os.unlink(temp_dest)
                        return False, None, f"Chunk {chunk_info['chunk_id']} integrity check failed"
                    
                    # Write chunk to output
                    output_file.write(chunk_data)
                    chunks_transferred += 1
            
            # Verify complete file integrity
            temp_file_hash = self._calculate_file_hash(temp_dest, self.integrity_algorithm)
            if temp_file_hash != manifest.file_sha256:
                os.unlink(temp_dest)
                return False, None, "Complete file integrity check failed"
            
            # Fsync and atomic move
            with open(temp_dest, 'rb') as f:
                os.fsync(f.fileno())
            
            shutil.move(temp_dest, destination)
            
            # Set permissions if specified
            if mode is not None:
                os.chmod(destination, mode)
            
            # Set ownership if specified (requires appropriate permissions)
            if owner or group:
                try:
                    import pwd, grp
                    uid = pwd.getpwnam(owner).pw_uid if owner else -1
                    gid = grp.getgrnam(group).gr_gid if group else -1
                    os.chown(destination, uid, gid)
                except (KeyError, PermissionError):
                    # Continue if ownership change fails
                    pass
            
            # If this was a compressed archive and original was a directory, extract it
            if manifest.metadata and manifest.metadata.get('is_directory') and manifest.compression:
                if destination.endswith(('.tar.gz', '.tgz')):
                    extract_dir = os.path.dirname(destination)
                    with tarfile.open(destination, 'r:gz') as tar:
                        tar.extractall(extract_dir)
                    os.unlink(destination)  # Remove archive after extraction
            
            transfer_time = time.time() - start_time
            
            # Create transfer result
            result = TransferResult(
                success=True,
                operation_id=manifest.operation_id,
                file_path=destination,
                total_size=manifest.total_size,
                chunks_transferred=chunks_transferred,
                transfer_time=transfer_time,
                integrity_verified=True
            )
            
            # Cleanup chunks
            self._cleanup_operation(manifest.operation_id)
            
            return True, result, ""
            
        except Exception as e:
            # Cleanup on error
            temp_dest = f"{destination}.tmp.{manifest.operation_id}"
            if os.path.exists(temp_dest):
                os.unlink(temp_dest)
            
            transfer_time = time.time() - start_time
            result = TransferResult(
                success=False,
                operation_id=manifest.operation_id,
                file_path=destination,
                total_size=manifest.total_size,
                chunks_transferred=chunks_transferred,
                transfer_time=transfer_time,
                integrity_verified=False,
                error=str(e)
            )
            
            return False, result, f"Import failed: {str(e)}"
    
    def get_chunk_data(self, operation_id: str, chunk_id: int) -> Optional[bytes]:
        """Get data for a specific chunk."""
        chunk_path = self.temp_dir / f"{operation_id}_chunk_{chunk_id}"
        
        if not chunk_path.exists():
            return None
        
        try:
            with open(chunk_path, 'rb') as f:
                return f.read()
        except Exception:
            return None
    
    def list_pending_operations(self) -> List[FileManifest]:
        """List pending file operations."""
        manifests = []
        
        for manifest_file in self.temp_dir.glob("*_manifest.json"):
            try:
                with open(manifest_file, 'r') as f:
                    data = json.load(f)
                
                manifest = FileManifest(**data)
                manifests.append(manifest)
                
            except Exception:
                continue
        
        return manifests
    
    def _cleanup_operation(self, operation_id: str):
        """Clean up temporary files for an operation."""
        try:
            # Remove chunks
            for chunk_file in self.temp_dir.glob(f"{operation_id}_chunk_*"):
                chunk_file.unlink()
            
            # Remove manifest
            manifest_file = self.temp_dir / f"{operation_id}_manifest.json"
            if manifest_file.exists():
                manifest_file.unlink()
                
        except Exception:
            pass  # Ignore cleanup errors
    
    def cleanup_old_operations(self, max_age_hours: int = 24):
        """Clean up old temporary files."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for temp_file in self.temp_dir.iterdir():
            try:
                if temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
            except Exception:
                continue
    
    def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get detailed file information."""
        if not os.path.exists(path) or not self._is_safe_path(path):
            return None
        
        try:
            stat = os.stat(path)
            
            return {
                'path': path,
                'size': stat.st_size,
                'mode': oct(stat.st_mode),
                'uid': stat.st_uid,
                'gid': stat.st_gid,
                'mtime': stat.st_mtime,
                'ctime': stat.st_ctime,
                'is_file': os.path.isfile(path),
                'is_dir': os.path.isdir(path),
                'is_link': os.path.islink(path),
                'readable': os.access(path, os.R_OK),
                'writable': os.access(path, os.W_OK),
                'executable': os.access(path, os.X_OK)
            }
            
        except Exception:
            return None
    
    def format_transfer_progress(self, manifest: FileManifest, chunks_completed: int) -> str:
        """Format transfer progress for display."""
        progress_percent = (chunks_completed / manifest.chunk_count) * 100
        transferred_bytes = chunks_completed * manifest.chunk_size
        
        return f"""**📁 File Transfer Progress**

**Operation:** {manifest.operation_id}
**File:** {manifest.file_path}
**Size:** {self._format_bytes(manifest.total_size)}
**Progress:** {progress_percent:.1f}% ({chunks_completed}/{manifest.chunk_count} chunks)
**Transferred:** {self._format_bytes(transferred_bytes)}
**Integrity:** SHA-256 verification enabled"""
    
    def format_transfer_result(self, result: TransferResult) -> str:
        """Format transfer result for display."""
        status_emoji = "✅" if result.success else "❌"
        
        message = f"""{status_emoji} **File Transfer Result**

**Operation:** {result.operation_id}
**File:** {result.file_path}
**Size:** {self._format_bytes(result.total_size)}
**Chunks:** {result.chunks_transferred}
**Time:** {result.transfer_time:.2f}s
**Integrity:** {'✅ Verified' if result.integrity_verified else '❌ Failed'}"""

        if result.error:
            message += f"\n**Error:** {result.error}"
        
        return message
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"

# Export
__all__ = ["FileChunk", "FileManifest", "TransferResult", "FileOps"]
