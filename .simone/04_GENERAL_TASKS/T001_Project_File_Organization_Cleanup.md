---
task_id: T001
task_type: general
status: not_started
priority: medium
complexity: Low
created: 2025-06-23 07:05:19
updated: 2025-06-23 07:05:19
assignee: automated
---

# Task: Project File Organization Cleanup & Workflow Compliance

## Context

This task addresses file organization issues identified during the 2025-06-23 project review. The current project structure has development files scattered in the root directory, violating the established workflow patterns and making the project harder to navigate and maintain.

**Related Documentation:**
- [Project Review 2025-06-23](../.simone/10_STATE_OF_PROJECT/2025-06-23-07-03-sprint-nearing-completion.md)
- [Project Manifest](../.simone/00_PROJECT_MANIFEST.md)

## Requirements

### File Organization Violations to Fix
1. **Development Scripts in Root**: Move `config.py`, `main.py`, `run_dashboard.py`, `send_completion_email.py` to proper locations
2. **Documentation Misplacement**: Relocate `SPRINT_EXECUTION_PLAN.md`, `SPRINT_TASKS.md`, `S01_M02_DASHBOARD_CORE_FEATURES_TASKS.md` to `.simone/01_PROJECT_DOCS/`
3. **Version Control Hygiene**: Add log files (`influence_item.log`, `firebase-debug.log`) to `.gitignore`
4. **Test File Placement**: Verify `test_schema_integration.py` belongs in `tests/` directory

### Workflow Compliance Goals
- All development scripts should follow established patterns
- Documentation should be properly organized
- Root directory should only contain essential project files
- Development artifacts should not be tracked in version control

## Acceptance Criteria

- [ ] Root directory contains only essential files (README, requirements.txt, main entry points)
- [ ] All development scripts are properly organized or removed
- [ ] Sprint documentation moved to appropriate `.simone/` subdirectories  
- [ ] Log files added to `.gitignore` and removed from version control
- [ ] File moves preserve git history where possible
- [ ] All imports and references updated after file moves
- [ ] Project still builds and runs after reorganization

## Dependencies

- **Prerequisite**: None
- **Blocks**: Future sprint work (cleaner development environment)
- **References**: Project Review findings from 2025-06-23

## Technical Guidance

### Key Integration Points
- **Main Entry Points**: Verify `main.py` and `run_dashboard.py` functionality after moves
- **Configuration System**: Update any hardcoded paths referencing moved files
- **Test Infrastructure**: Ensure test discovery still works after moving test files
- **Documentation Links**: Update relative paths in documentation after moves

### Existing Patterns to Follow
- **Development Scripts**: Should integrate with or be consolidated into `run_dev.py` pattern
- **Documentation Structure**: Follow `.simone/01_PROJECT_DOCS/` organization
- **Configuration Files**: Keep environment-specific config in root, move development config to `config/`
- **Git Ignore Patterns**: Follow existing `.gitignore` structure for log files

### File Movement Strategy
1. **Preserve Git History**: Use `git mv` for important files
2. **Batch Related Changes**: Group related file moves in single commits
3. **Test After Each Move**: Verify functionality is preserved
4. **Update Imports**: Check for relative imports that break after moves

## Implementation Notes

### Step-by-Step Approach
1. **Audit Current Files**: Create inventory of files to move/remove/update
2. **Plan Move Strategy**: Determine destination for each misplaced file
3. **Update Imports**: Identify and fix import statements affected by moves
4. **Execute Moves**: Use `git mv` to preserve history
5. **Update Documentation**: Fix relative paths and references
6. **Clean Git History**: Remove log files and add to `.gitignore`
7. **Verify Functionality**: Test that core features still work
8. **Update Project Manifest**: Reflect any changes to project structure

### Testing Approach
- Run main application (`run_dashboard.py`) to verify dashboard functionality
- Execute test suite to ensure tests still discover and run properly
- Check that configuration loading works after `config.py` move
- Verify documentation links are not broken

### Files to Investigate
- `config.py` - Determine if this should be in `src/config/` or `config/`
- `main.py` - Check if this is a legitimate entry point or development artifact
- `test_schema_integration.py` - Verify this belongs in `tests/` directory
- Sprint documentation files - Move to `.simone/01_PROJECT_DOCS/sprints/`

## Output Log

*(This section will be populated as work progresses on the task)*