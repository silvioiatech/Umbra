"""
Docker Registry Helper - Utilities for interacting with Docker images and registries
Provides functionality to check image versions, get digests, and parse version information.
"""
import re
import json
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin
import subprocess

from ...core.config import UmbraConfig


@dataclass
class ImageInfo:
    repository: str
    tag: str
    digest: str
    created: str
    size: int
    labels: Dict[str, str]


@dataclass
class VersionInfo:
    major: int
    minor: int
    patch: int
    pre_release: Optional[str]
    build: Optional[str]
    major_jump: bool = False
    minor_jump: bool = False
    patch_jump: bool = False


class DockerRegistryHelper:
    """Helper class for Docker registry operations and image management."""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Docker command configurations
        self.docker_cmd = config.get('DOCKER_CMD', 'docker')
        self.timeout = config.get('DOCKER_TIMEOUT', 30)
        
        # Registry configurations
        self.default_registry = config.get('DEFAULT_DOCKER_REGISTRY', 'docker.io')
        self.registry_auth = config.get('DOCKER_REGISTRY_AUTH', {})
        
        # Version parsing patterns
        self.version_patterns = [
            r'^v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*))?(?:\+([a-zA-Z0-9]+))?$',  # Semantic version
            r'^v?(\d+)\.(\d+)(?:-([a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*))?$',  # Major.minor
            r'^v?(\d+)(?:-([a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*))?$',  # Major only
            r'^(\d{4})\.(\d{2})\.(\d{2})$',  # Date-based (YYYY.MM.DD)
        ]

    async def get_current_image_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get current image information for a running service."""
        try:
            # Get container info
            cmd = [
                self.docker_cmd, 'ps', 
                '--filter', f'name={service_name}',
                '--format', 'json'
            ]
            
            result = await self._run_docker_command(cmd)
            if not result or not result.strip():
                self.logger.warning(f"No running container found for service {service_name}")
                return None
            
            # Parse container info
            container_info = json.loads(result.strip().split('\n')[0])  # First container
            container_id = container_info['ID']
            
            # Get image details
            cmd = [
                self.docker_cmd, 'inspect', container_id,
                '--format', '{{json .Config.Image}}'
            ]
            
            image_result = await self._run_docker_command(cmd)
            if not image_result:
                return None
            
            image_name = json.loads(image_result.strip())
            
            # Parse image name
            repository, tag = self._parse_image_name(image_name)
            
            # Get image digest
            digest = await self._get_image_digest(image_name)
            
            return {
                'service_name': service_name,
                'repository': repository,
                'tag': tag,
                'digest': digest,
                'image_name': image_name,
                'container_id': container_id
            }
            
        except Exception as e:
            self.logger.error(f"Error getting current image info for {service_name}: {e}")
            return None

    async def get_remote_image_info(self, repository: str, tag: str) -> Optional[Dict[str, Any]]:
        """Get remote image information from registry."""
        try:
            image_name = f"{repository}:{tag}"
            
            # Use docker manifest inspect to get remote digest
            cmd = [
                self.docker_cmd, 'manifest', 'inspect', image_name,
                '--verbose'
            ]
            
            result = await self._run_docker_command(cmd)
            if not result:
                return None
            
            manifest_data = json.loads(result)
            
            # Extract digest from manifest
            digest = None
            if isinstance(manifest_data, list):
                # Multi-platform manifest
                for item in manifest_data:
                    if item.get('Descriptor', {}).get('digest'):
                        digest = item['Descriptor']['digest']
                        break
            elif manifest_data.get('Descriptor', {}).get('digest'):
                digest = manifest_data['Descriptor']['digest']
            
            if not digest:
                self.logger.warning(f"Could not extract digest for {image_name}")
                return None
            
            return {
                'repository': repository,
                'tag': tag,
                'digest': digest,
                'image_name': image_name
            }
            
        except Exception as e:
            self.logger.error(f"Error getting remote image info for {repository}:{tag}: {e}")
            return None

    async def _get_image_digest(self, image_name: str) -> Optional[str]:
        """Get the digest of a local image."""
        try:
            cmd = [
                self.docker_cmd, 'inspect', image_name,
                '--format', '{{index .RepoDigests 0}}'
            ]
            
            result = await self._run_docker_command(cmd)
            if not result or result.strip() == '<no value>':
                return None
            
            # Extract digest from repo digest (format: repo@sha256:...)
            repo_digest = result.strip()
            if '@' in repo_digest:
                return repo_digest.split('@')[1]
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Could not get digest for {image_name}: {e}")
            return None

    def _parse_image_name(self, image_name: str) -> Tuple[str, str]:
        """Parse repository and tag from image name."""
        if ':' in image_name:
            repository, tag = image_name.rsplit(':', 1)
        else:
            repository = image_name
            tag = 'latest'
        
        # Handle registry prefix
        if '/' not in repository:
            repository = f"library/{repository}"
        
        return repository, tag

    async def pull_image(self, repository: str, tag: str) -> bool:
        """Pull an image from the registry."""
        image_name = f"{repository}:{tag}"
        
        try:
            self.logger.info(f"Pulling image {image_name}")
            
            cmd = [self.docker_cmd, 'pull', image_name]
            result = await self._run_docker_command(cmd, timeout=300)  # 5 minute timeout
            
            if result is not None:
                self.logger.info(f"Successfully pulled {image_name}")
                return True
            else:
                self.logger.error(f"Failed to pull {image_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error pulling image {image_name}: {e}")
            return False

    async def get_available_tags(self, repository: str, limit: int = 10) -> List[str]:
        """Get available tags for a repository."""
        try:
            # This is a simplified implementation
            # In a real scenario, you might want to use registry API
            
            # For now, we'll use docker search or assume common patterns
            common_tags = ['latest', 'stable', 'main', 'master']
            
            # Try to get version-like tags
            version_tags = []
            for i in range(limit):
                # Generate some common version patterns
                version_tags.extend([
                    f"1.{i}.0",
                    f"2.{i}.0",
                    f"v1.{i}.0",
                    f"v2.{i}.0"
                ])
            
            return common_tags + version_tags[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting available tags for {repository}: {e}")
            return []

    async def parse_version_info(self, tag: str, repository: str) -> Optional[VersionInfo]:
        """Parse version information from a tag."""
        try:
            # Try each version pattern
            for pattern in self.version_patterns:
                match = re.match(pattern, tag)
                if match:
                    groups = match.groups()
                    
                    # Extract version components
                    major = int(groups[0]) if groups[0] else 0
                    minor = int(groups[1]) if len(groups) > 1 and groups[1] else 0
                    patch = int(groups[2]) if len(groups) > 2 and groups[2] else 0
                    
                    pre_release = None
                    build = None
                    
                    # Handle pre-release and build metadata
                    if len(groups) > 3 and groups[3]:
                        pre_release = groups[3]
                    if len(groups) > 4 and groups[4]:
                        build = groups[4]
                    
                    return VersionInfo(
                        major=major,
                        minor=minor,
                        patch=patch,
                        pre_release=pre_release,
                        build=build
                    )
            
            # If no pattern matches, try to extract numbers
            numbers = re.findall(r'\d+', tag)
            if numbers:
                major = int(numbers[0])
                minor = int(numbers[1]) if len(numbers) > 1 else 0
                patch = int(numbers[2]) if len(numbers) > 2 else 0
                
                return VersionInfo(
                    major=major,
                    minor=minor,
                    patch=patch,
                    pre_release=None,
                    build=None
                )
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error parsing version from tag {tag}: {e}")
            return None

    async def compare_versions(self, current_tag: str, target_tag: str, repository: str) -> Optional[VersionInfo]:
        """Compare two versions and return comparison info."""
        try:
            current_version = await self.parse_version_info(current_tag, repository)
            target_version = await self.parse_version_info(target_tag, repository)
            
            if not current_version or not target_version:
                return None
            
            # Create comparison result
            result = VersionInfo(
                major=target_version.major,
                minor=target_version.minor,
                patch=target_version.patch,
                pre_release=target_version.pre_release,
                build=target_version.build
            )
            
            # Determine jump types
            if target_version.major > current_version.major:
                result.major_jump = True
            elif target_version.major == current_version.major:
                if target_version.minor > current_version.minor:
                    result.minor_jump = True
                elif target_version.minor == current_version.minor:
                    if target_version.patch > current_version.patch:
                        result.patch_jump = True
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error comparing versions {current_tag} vs {target_tag}: {e}")
            return None

    async def get_release_info(self, repository: str, tag: str) -> Tuple[Optional[str], Optional[str]]:
        """Get release notes and changelog URL for a version."""
        try:
            # This is a placeholder implementation
            # In a real scenario, you might want to:
            # 1. Query GitHub API for release notes
            # 2. Check Docker Hub API for image metadata
            # 3. Parse labels from the image
            
            release_notes = None
            changelog_url = None
            
            # Try to get image labels that might contain release info
            image_name = f"{repository}:{tag}"
            cmd = [
                self.docker_cmd, 'inspect', image_name,
                '--format', '{{json .Config.Labels}}'
            ]
            
            result = await self._run_docker_command(cmd)
            if result:
                labels = json.loads(result.strip())
                
                # Look for common label keys
                release_notes = (labels.get('org.opencontainers.image.description') or
                               labels.get('org.label-schema.description') or
                               labels.get('release.notes'))
                
                changelog_url = (labels.get('org.opencontainers.image.url') or
                               labels.get('org.label-schema.url') or
                               labels.get('changelog.url'))
            
            # Generate GitHub-style URLs for common repositories
            if not changelog_url and 'n8n' in repository.lower():
                changelog_url = f"https://github.com/n8n-io/n8n/releases/tag/{tag}"
            
            return release_notes, changelog_url
            
        except Exception as e:
            self.logger.debug(f"Error getting release info for {repository}:{tag}: {e}")
            return None, None

    async def _run_docker_command(self, cmd: List[str], timeout: Optional[int] = None) -> Optional[str]:
        """Run a docker command and return the output."""
        try:
            timeout = timeout or self.timeout
            
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                self.logger.error(f"Docker command timed out after {timeout}s: {' '.join(cmd)}")
                return None
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                self.logger.error(f"Docker command failed with code {process.returncode}: {error_msg}")
                return None
            
            return stdout.decode().strip()
            
        except Exception as e:
            self.logger.error(f"Error running docker command: {e}")
            return None

    async def check_image_exists(self, repository: str, tag: str) -> bool:
        """Check if an image exists locally."""
        try:
            image_name = f"{repository}:{tag}"
            cmd = [self.docker_cmd, 'inspect', image_name]
            
            result = await self._run_docker_command(cmd)
            return result is not None
            
        except Exception:
            return False

    async def remove_image(self, repository: str, tag: str, force: bool = False) -> bool:
        """Remove a local image."""
        try:
            image_name = f"{repository}:{tag}"
            cmd = [self.docker_cmd, 'rmi', image_name]
            
            if force:
                cmd.append('--force')
            
            result = await self._run_docker_command(cmd)
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Error removing image {repository}:{tag}: {e}")
            return False

    async def get_image_history(self, repository: str, tag: str) -> List[Dict[str, Any]]:
        """Get the history of an image."""
        try:
            image_name = f"{repository}:{tag}"
            cmd = [
                self.docker_cmd, 'history', image_name,
                '--format', 'json', '--no-trunc'
            ]
            
            result = await self._run_docker_command(cmd)
            if not result:
                return []
            
            history = []
            for line in result.strip().split('\n'):
                if line.strip():
                    history.append(json.loads(line))
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting image history for {repository}:{tag}: {e}")
            return []

    def get_status(self) -> Dict[str, Any]:
        """Get Docker registry helper status."""
        return {
            "docker_cmd": self.docker_cmd,
            "timeout": self.timeout,
            "default_registry": self.default_registry,
            "version_patterns": len(self.version_patterns),
            "registry_auth_configured": bool(self.registry_auth)
        }
