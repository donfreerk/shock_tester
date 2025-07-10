# Development Directory

This directory contains development, debug, and prototype files that are not part of the main application.

## Structure

- `scripts/` - Utility scripts for development and debugging
- `tests/` - Experimental tests and test utilities  
- `prototypes/` - Prototype implementations and experiments
- `debug/` - Debug files, temporary fixes, and investigation code
- `temp/` - Temporary files (excluded from git)

## Usage

Files in this directory are:
- ✅ Safe to modify during development
- ✅ Excluded from production builds
- ⚠️ May be experimental or incomplete
- ❌ Should not be imported by main application code

## Cleanup Policy

- `temp/` is excluded from git and can be safely deleted
- Other directories contain development history and should be preserved
- Before deleting anything, check if it's referenced in documentation or issues
