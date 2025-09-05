# Concierge Instances Registry

## Overview

The Concierge module now includes a comprehensive instances registry that provides infrastructure management capabilities with full Business gateway integration. This allows for centralized management of VPS instances, containers, databases, and other infrastructure components.

## Features

### Core Functionality
- **Create Instance**: Provision new infrastructure instances with customizable resources
- **List Instances**: View all registered instances with status and client information
- **Delete Instance**: Safely decommission instances with proper cleanup
- **Instance Status**: Get detailed information about specific instances

### Business Integration
- **Gateway Operations**: All instance operations can be performed through the Business module
- **Client Association**: Instances can be linked to business clients for billing and management
- **Action Logging**: All operations are logged for audit and business intelligence
- **Revenue Tracking**: Automatic integration with business revenue calculations

## Database Schema

The instances registry uses a dedicated `instances` table:

```sql
CREATE TABLE instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT UNIQUE NOT NULL,           -- Generated unique identifier
    name TEXT NOT NULL,                         -- Human-readable name
    instance_type TEXT NOT NULL,                -- Type: vps, container, database, etc.
    status TEXT DEFAULT 'pending',              -- Status: pending, active, error, etc.
    client_id INTEGER,                          -- Link to clients table
    resources TEXT,                             -- JSON: CPU, memory, disk, etc.
    config TEXT,                                -- JSON: Instance-specific configuration
    ip_address TEXT,                            -- Assigned IP address
    port INTEGER,                               -- Assigned port
    created_by TEXT,                            -- Who created the instance
    metadata TEXT,                              -- Additional JSON metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Usage Examples

### Direct Concierge Operations

```python
# Create an instance
await concierge.create_instance(
    instance_name="web-server",
    instance_type="vps", 
    client_id=1,
    resources={"cpu": 4, "memory": 8, "disk": 100}
)

# List all instances
await concierge.list_instances()

# Delete an instance
await concierge.delete_instance("vps-web-server-abc123")

# Get instance status
await concierge.get_instance_status("vps-web-server-abc123")
```

### Business Gateway Operations

```python
# Create instance via Business gateway
await business.gateway_create_instance(
    instance_name="production-db",
    instance_type="database",
    client_name="Tech Solutions Inc",
    resources={"cpu": 8, "memory": 16, "disk": 500}
)

# List instances with business context
await business.gateway_list_instances()

# Delete instance with business logging
await business.gateway_delete_instance("database-production-db-xyz789")
```

## Command Integration

The functionality is integrated into the command handlers:

### Concierge Commands
- `create instance <name> [type] [resources]`
- `list instances`
- `delete instance <id>`
- `instance status <id>`

### Business Gateway Commands
- `create instance <name> [type] [client] [resources]` (via Business module)
- `list instances` (via Business module)
- `delete instance <id>` (via Business module)

## Implementation Details

### Instance ID Generation
Instance IDs are automatically generated using the pattern:
`{type}-{name-kebab-case}-{random-6-chars}`

Example: `vps-web-server-abc123`

### Resource Management
Resources are stored as JSON and include:
- `cpu`: Number of CPU cores
- `memory`: RAM in GB
- `disk`: Storage in GB
- `bandwidth`: Monthly bandwidth limit in GB

### Status Lifecycle
1. **pending**: Instance is being provisioned
2. **active**: Instance is running and available
3. **error**: Instance encountered an error
4. **terminated**: Instance has been decommissioned

### Business Actions Logging
All operations performed through the Business gateway are logged in the `business_actions` table for:
- Audit trails
- Business intelligence
- Billing integration
- Client reporting

## Error Handling

The implementation includes comprehensive error handling:
- Validation of required fields
- Duplicate instance ID prevention
- Graceful handling of database errors
- Proper cleanup on failures

## Security Considerations

- Instance operations require proper authentication
- Resource limits can be enforced based on business rules
- Client isolation ensures data security
- Audit logging provides accountability

## Future Enhancements

Potential future improvements:
- Real-time monitoring integration
- Automated scaling policies
- Cost optimization recommendations
- Integration with cloud providers
- Backup and disaster recovery automation