# Instance Management Commands

The Business module provides instance management commands through the `/inst` interface. These commands manage VPS client n8n instances via the Concierge module.

## Available Commands

### `/inst help`
Display the complete command reference and examples.

### Create Instance Commands

#### Basic Creation (Auto-assign Port)
```
create instance <client>
```
Example: `create instance acme-corp`

#### Create with Custom Display Name
```
create instance <client> name "Display Name"
```
Example: `create instance startup-x name "Startup X n8n"`

#### Create with Specific Port
```
create instance <client> port <port_number>
```
Example: `create instance test-env port 20050`

### List and View Commands

#### List All Instances
```
list instances
```
Shows a summary of all client instances with status and ports.

#### Show Instance Details
```
show instance <client>
```
Example: `show instance acme-corp`
Shows detailed information including data directory and reserved status.

### Delete Commands (Admin Only)

#### Archive Instance (Keep Data)
```
delete instance <client> keep
```
Example: `delete instance test-env keep`
- Removes container but preserves data
- Reserves the port (prevents auto-allocation)
- Status becomes "archived"

#### Permanently Delete Instance
```
delete instance <client> wipe
```
Example: `delete instance test-env wipe`
- Completely removes instance and data
- Frees the port for reuse
- Cannot be undone

## Business Module Architecture

### Thin Gateway Pattern
The Business module acts as a **thin gateway** between Telegram and the Concierge module:

- **No Storage**: Business stores nothing, all data lives in Concierge
- **Validation Only**: Business validates parameters and forwards to Concierge
- **Formatting**: Business formats Concierge responses for Telegram
- **Pass-through**: All execution happens in Concierge

### Key Features

#### Parameter Validation
- **Client Slug**: Must be `[a-z0-9-]` and max 32 characters
- **Port Range**: Configurable range (default: 20000-21000)
- **Mode Validation**: Delete mode must be "keep" or "wipe"

#### Security
- **Admin-only Deletion**: Delete operations require admin permissions
- **Audit Trail**: All operations include audit IDs from Concierge
- **Error Forwarding**: Concierge errors are surfaced verbatim

#### Idempotency
- **Create Instance**: Creating existing instance returns current details
- **Port Management**: Auto-allocation skips reserved ports
- **Status Tracking**: Instances can be active, archived, or inactive

## Configuration

### Environment Variables
```bash
CLIENT_PORT_RANGE="20000-21000"  # Port allocation range
ALLOWED_ADMIN_IDS="123,456"      # Admin user IDs for delete operations
```

### Instance Registry Schema
```sql
instance_registry (
  id INTEGER PRIMARY KEY,
  client_id TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  url TEXT NOT NULL,
  port INTEGER UNIQUE NOT NULL,
  status TEXT DEFAULT 'active',
  data_dir TEXT,
  reserved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

## Example Workflow

1. **Create Instance**: `create instance acme-corp name "Acme Corp N8N"`
2. **Verify Creation**: `show instance acme-corp`
3. **List All**: `list instances`
4. **Archive When Done**: `delete instance acme-corp keep` (admin only)
5. **Permanent Cleanup**: `delete instance acme-corp wipe` (admin only)

All operations include audit IDs for tracking and compliance.