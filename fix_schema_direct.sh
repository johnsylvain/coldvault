#!/bin/bash
# Direct SQL fix for database schema - no container rebuild needed

echo "Fixing database schema directly via psql..."

# Get database password from environment or use default
DB_PASSWORD=${DB_PASSWORD:-changeme}

# Run SQL directly in the database container
docker compose exec -T db psql -U coldvault -d coldvault <<EOF
-- Fix backup_runs.size_bytes
ALTER TABLE backup_runs ALTER COLUMN size_bytes TYPE BIGINT;

-- Fix snapshots.size_bytes  
ALTER TABLE snapshots ALTER COLUMN size_bytes TYPE BIGINT;

-- Verify the changes
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name IN ('backup_runs', 'snapshots') 
  AND column_name = 'size_bytes';
EOF

echo ""
echo "Schema fix complete!"
echo ""
echo "Now recover the backup run:"
echo "  docker compose exec coldvault python fix_database_and_recover.py --recover 3"
