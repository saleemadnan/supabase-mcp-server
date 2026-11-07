# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).


## [Unreleased]
### Fixed
- A final SQL statement without a trailing `;` was silently skipped (`execute_postgresql("SELECT 1")` returned `results=[]`, and an unterminated DDL in unsafe mode recorded a migration without running). The statement text now extends to the end of the input.
- Two schema changes within the same second no longer lose a migration record: migration versions are now unique and increasing within the process (still `YYYYMMDDHHMMSS`).
- Migration names for `CREATE TABLE`/`ALTER TABLE` now use the table name instead of `unknown` or a trailing keyword.
- A denied Pro-plan feature now reports the plan message instead of "We couldn't verify access ... at the moment".


## [0.3.12] - 2025-03-12
### Added
- Implemented a new `retrieve_logs` tool that allows retrieval of logs from any Supabase log collection - Postgres, PostgREST, Auth, Edge Functions and others. Provides a way to query and filter
- Implemented log rotation to prevent unbounded log file growth (5MB limit with 3 backup files)

### Changed
- Improved region configuration with clearer error messages for region mismatches
- Updated smithery.yaml to reduce configuration error rate (Tenant not found)
- Improved PostgreSQL client connection error handling with specific guidance for "Tenant or user not found" errors


## [0.3.11] - 2025-03-10
### Fixed
- Fixed an error with creating a migration file when a user doesn't have `supabase_migrations` schema


## [0.3.10] - 2025-03-09
### Added
- Enhanced migration naming system with improved object type detection for procedures, functions, and views.
- Expanded `retrieve_migrations` tool with pagination, name pattern filtering, and option to include full SQL queries.
- Added a check to validate personal access token and service role key are set before calling API or SDK methods

### Changed
- Updated setup instructions for Claude Desktop
- Updated setup instructions for Cline
- Updated and fixed Smithery.ai setup

### Removed
- Removed redundant `get_api_safety_rules` tool since exceptions already provide enough information to the client


## [0.3.9] - 2025-03-08
### Fixed
- Fixed an issue with api spec tool that prevented spec retrieval


## [0.3.8] - 2025-03-07
### Added
- SQL query validation using PostgreSQL's parser (pglast v7.3+)
- Automatic migration script generation for schema changes
- Universal safety system with standardized risk levels (Low/Medium/High/Extreme)
- Switched to asyncpg v0.30.0+ from psycopg2
- Enhanced API spec tool with multiple query modes and risk assessment
- Connection retry logic for database and API operations
- Code coverage with pytest-cov
- SQL linting with SQLFluff
- Added pyyaml v6.0.2+ for configuration

### Changed
- Refactored to use dependency injection pattern
- Standardized service initialization to synchronous pattern
- Improved SQL safety categorization:
  - `safe`: Read-only operations (always allowed)
  - `write`: Data modification (requires unsafe mode)
  - `destructive`: Schema changes (requires unsafe mode + confirmation)
- Updated Ruff to v0.9.9
- Added asyncpg-stubs and pytest-mock for testing

## [0.3.7] - 2025-03-02
### Fixed
- Documentation inaccuracies

### Added
- Auth admin SDK support for local Supabase instances


## [0.3.6] - 2025-02-26
### Added
- Added `call_auth_admin_method` which enables MCP server to manage users in your database (create, update, delete, confirm). All Auth SDK methods are supported
- Added `get_auth_admin_methods_spec` to retrieve documentation for all available Auth Admin methods. Response objects now use attribute access (dot notation) instead of dictionary access.

### Fixed
- Fixed an issue with improper encoding of database passwords. Previously passwords containing "%" symbol led to connection failures


## [0.3.5] - 2025-02-26
### Fixed
- Fixed an issue with `get_tables` so that it reliably returns foreign tables and views
- Updated docs to describe how to setup mcp.json with project-specific MCPs
- Expanded and improved test suite to cover each MCP tool


## [0.3.4] - 2025-02-25
### Fixed
- Improved `get_tables` to return foreign data tables


## [0.3.3] - 2025-02-25
### Fixed
- Fixed a bug with `readonly` scope being incorrectly managed in db client

## [0.3.2] - 2025-02-25
### Fixed
- Fixed a bug preventing execution of DDL commands (create, alter tables, etc.)

## [0.3.1] - 2025-02-23
### Changed
- Significantly improved docs to make install, configuration, usage instructions super clear


## [0.3.0] - 2025-02-23
### Added
- Full support for read-write SQL operations:
  - Implemented safety mode system with read-only (default) and read-write modes
  - Added mode switching with automatic reset to read-only
  - Enhanced transaction support for testing write operations
  - Improved error handling for read-only violations
- Support for Supabase Management API
  - Introduces supabase management API integration with safe (enabled by default) and yolo modes
  - Includes the following tools:
    - `send_management_api_request` to send arbitrary requests to Supabase Management API, with auto-injection of project ref and safety mode control.
    - `get_management_api_spec` to get the enriched API specification with safety information
    - `get_management_api_safety_rules` to get all safety rules including blocked and unsafe operations with human-readable explanations
    - `live_dangerously` to switch to yolo mode
  - Safety features:
    - Divides API methods into `safe`, `unsafe` and `blocked` categories based on the risk of the operation
    - Allows to switch between safe and yolo modes dynamically
    - Blocked operations (delete project, delete database) are not allowed regardless of the mode


## [0.2.2] - 2025-02-20
### Added
- Support for different Supabase regions:
  - Configuration via `SUPABASE_REGION` environment variable
  - Validation for all 16 supported AWS regions
  - Default to `us-east-1` for backward compatibility
  - Enhanced logging for region information
  - Comprehensive documentation and examples

## [0.2.1] - 2025-02-19
### Added
- Package distribution support:
  - PyPI package publishing setup
  - Installation via `pipx` and `uv`
  - Entry point scripts for direct execution
- Smithery.ai deployment configuration

### Changed
- BREAKING: Installation and execution methods:
  - Switched from direct script execution to proper module structure
  - Updated Cursor/Windsurf configuration for package-based execution
- Improved setup instructions in README

## [0.2.0] - 2025-02-18
Intermediary release for package distribution support

## [0.1.0] - 2025-02-16
### Added
- Initial release
- Basic MCP server functionality
- Supabase database connection support
- Integration with Cursor and Windsurf IDEs

[0.3.0]: https://github.com/alexander-zuev/supabase-mcp-server/releases/tag/v0.3.0
[0.2.2]: https://github.com/alexander-zuev/supabase-mcp-server/releases/tag/v0.2.2
[0.2.1]: https://github.com/alexander-zuev/supabase-mcp-server/releases/tag/v0.2.1
[0.2.0]: https://github.com/alexander-zuev/supabase-mcp-server/releases/tag/v0.2.0-dev0
[0.1.0]: https://github.com/alexander-zuev/supabase-mcp-server/releases/tag/v0.1.0
