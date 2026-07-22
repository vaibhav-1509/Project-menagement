-- Migration for file transfer progress tracking and admin source path
-- Run against existing database if needed

-- Add progress tracking columns to FileTransferLog
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'FileTransferLog' AND COLUMN_NAME = 'BytesCopied')
BEGIN
    ALTER TABLE FileTransferLog ADD BytesCopied BIGINT NULL;
    PRINT 'Added BytesCopied column to FileTransferLog';
END

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'FileTransferLog' AND COLUMN_NAME = 'TotalBytes')
BEGIN
    ALTER TABLE FileTransferLog ADD TotalBytes BIGINT NULL;
    PRINT 'Added TotalBytes column to FileTransferLog';
END

-- Add AdminSourcePath to AppSettings
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'AppSettings' AND COLUMN_NAME = 'AdminSourcePath')
BEGIN
    ALTER TABLE AppSettings ADD AdminSourcePath NVARCHAR(500) NULL;
    PRINT 'Added AdminSourcePath column to AppSettings';
END