CREATE TABLE IF NOT EXISTS material_batches (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(32) NOT NULL UNIQUE,
    sku_code VARCHAR(64) NOT NULL,
    image_1 VARCHAR(512),
    image_2 VARCHAR(512),
    image_3 VARCHAR(512),
    image_4 VARCHAR(512),
    cover_image VARCHAR(512),
    tags TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account_devices (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL UNIQUE,
    account_name VARCHAR(128) NOT NULL,
    platform VARCHAR(32) NOT NULL DEFAULT 'dewu',
    device_id VARCHAR(64) NOT NULL UNIQUE,
    device_name VARCHAR(128),
    adb_serial VARCHAR(128),
    appium_url VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'idle',
    last_heartbeat TIMESTAMPTZ,
    remark TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS publish_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) NOT NULL UNIQUE,
    platform VARCHAR(32) NOT NULL DEFAULT 'dewu',
    sku_code VARCHAR(64) NOT NULL,
    account_id VARCHAR(64),
    device_id VARCHAR(64),
    material_batch_id VARCHAR(64),
    title VARCHAR(255) NOT NULL,
    content TEXT,
    topics TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    current_step VARCHAR(128),
    plan_publish_time TIMESTAMPTZ,
    actual_publish_time TIMESTAMPTZ,
    execution_started_at TIMESTAMPTZ,
    execution_finished_at TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    publish_url VARCHAR(512),
    result_screenshot VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_publish_tasks_material_batch
        FOREIGN KEY (material_batch_id) REFERENCES material_batches (batch_id),
    CONSTRAINT fk_publish_tasks_account
        FOREIGN KEY (account_id) REFERENCES account_devices (account_id),
    CONSTRAINT fk_publish_tasks_device
        FOREIGN KEY (device_id) REFERENCES account_devices (device_id)
);

CREATE TABLE IF NOT EXISTS publish_logs (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(32) NOT NULL,
    step_name VARCHAR(128) NOT NULL,
    result VARCHAR(32) NOT NULL,
    detail TEXT,
    screenshot VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_publish_logs_task
        FOREIGN KEY (task_id) REFERENCES publish_tasks (task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_publish_tasks_status ON publish_tasks (status);
CREATE INDEX IF NOT EXISTS idx_publish_tasks_device ON publish_tasks (device_id);
CREATE INDEX IF NOT EXISTS idx_publish_logs_task_id ON publish_logs (task_id);
CREATE INDEX IF NOT EXISTS idx_account_devices_status ON account_devices (status);
