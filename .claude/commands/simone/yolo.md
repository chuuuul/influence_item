# Execute all open tasks in YOLO mode

This mode is meant to be run without user interaction.
You **DO NOT** ask the user any questions or ask for confirmation
If in doubt you **RESEARCH** and **ULTRATHINK** about the best solution.

**IMPORTANT** you try not to stop at any certain point but do so if you need after thoughtful consideration.

Priority is to get the work completed.

## Mode Selection

Check <$ARGUMENTS>:

- If sprint ID provided (e.g., S03): Work ONLY on that sprint
- If empty: Work on general tasks first, then active sprint tasks

**Report Mode** to the User!

## Safety Guidelines

- **NEVER** modify critical files (.env, alembic migrations, production configs)
- **NEVER** .calude/commands 폴더의 내용을 추가/수정/제거 하지 말 것
- **STOP** if you encounter database schema changes
- **STOP** if you need to delete more than 5 files
- **STOP** if tests are failing after your changes
- **ALWAYS** run tests after implementing a task

## Follow this exact process

You need to stick to this process and **PRECISELY** follow it

Before you start:

- Run tests to ensure clean baseline using test.md command (@.claude/commands/simone/test.md)
- **If** FAIL rate is above 10% asses if a fix is possible. If so, fix and move on. If not, move on anyways.

- Check git status to ensure clean working directory
- **If** git status is not clean just remember and report to the user at the end, but move on.

Also consider <$ARGUMENTS> - if anything between <> can be considered additional instructions, prioritize them in the process.

Get the current datetime stamp from the system and remember it

- PRD.md 문서를 무조건 읽고 반드시 PRD문서에 정의 되어있는 기능만 구현 할 것.

### FIND OPEN WORK

Execute based on mode:

**If Sprint ID provided in arguments:**

- Navigate to .simone/03_SPRINTS/{sprint_id}/
- Check if sprint has tasks (T*.md files)
- If NO tasks exist:
  - Check for sprint meta file
  - If meta exists: Jump to ### CREATE SPRINT TASKS
  - If no meta: Exit with error - sprint doesn't exist
- If tasks exist: Continue to **Task selection** section below

**If NO arguments (general mode):**

- Use PARALLEL SUBAGENTS to check:
  - .simone/04_GENERAL_TASKS for open general tasks
  - .simone/00_PROJECT_MANIFEST.md for currently active sprint
  - .simone/03_SPRINTS/ for any sprint with only meta file
- Priority order:
  1. General tasks (if any open)
  2. Active sprint tasks (if any open)
  3. Sprint needing task creation (if found) - maintain order of Sprints

**Task Selection:**

- From found tasks, select ONE that is not completed. Take the lowest ID in Sprint or General Tasks
- Skip tasks you've previously attempted (check OUTPUT LOG)
- If no suitable task found and no sprint needs tasks: Exit gracefully

### CREATE SPRINT TASKS

**ONLY EXECUTE** if sprint needs task creation

- Use a **SUBAGENT** and have it include @.claude/commands/simone/create_sprint_tasks.md with Sprint ID as argument
- Wait for completion
- After task creation move back to `### FIND OPEN WORK`

### WORK ON TASK

- if you have touched this task before ignore it and jump to the next task
- if you can't find a task that you have not tried fixing before jump to ### EXECUTE PROJECT REVIEW
- if you find a task that you cannot fix because the work was done already, close the task and note in Output Log of task.
- **USE A SUBAGENT** and have it include @.claude/commands/simone/do_task.md with the Task ID as Argument to execute the Task.
- **AFTER TASK COMPLETION**: Run tests to verify nothing broke using test.md command (@.claude/commands/simone/test.md)
- on any failure in the task execution assess the severity of the error:
  - CRITICAL errors (breaking tests, security issues, data loss risk): **FIX PROBLEMS**
  - NON-CRITICAL errors (linting, formatting, minor issues): note in OUTPUT LOG and continue
- on success move on

### COMMIT WORK

- **ONLY IF** tests are passing and no critical issues exist
- **USE A SUBAGENT** and have it include @.claude/commands/simone/commit.md with the Task ID as Argument and YOLO as additional argument
- on any failure when committing, note the problem in the OUTPUT LOG of the task and continue
- after successful commit, merge to main: `git checkout main && git merge task/<task-id>`
- on success move on

### REPEAT FOR ALL OPEN TASKS

**Based on current mode:**

**Sprint-specific mode:**

- Continue with next task in the specified sprint only
- Go back to ### WORK ON TASK until all sprint tasks are done
- When sprint is complete, move to project review

**General mode:**

- After completing a general task, check for more general tasks first
- If no general tasks remain, move to active sprint tasks
- Continue until all accessible tasks are done
- When done move on

## EXECUTE PROJECT REVIEW

- **USE A SUBAGENT** and have it include @.claude/commands/simone/project_review.md
- Depending on the results of the review:
  - On FAIL: Think about possible fixes.
  - If fixes are quickly done, fix right away and repeat `## EXECUTE PROJECT REVIEW``
  - If fixes are more complex **USE A SUBAGENT** and have it include @.claude/commands/simone/create_general_task.md to create new general tasks as needed.
  - Go back to `### FIND OPEN WORK` to work on these fixes
  - On PASS: move on

## MORE WORK TO DO?

**Based on current mode:**

**Sprint-specific mode:**

Your work is done. Move to `## CREATE SUMMARY`

**General mode:**

- Move on to check for more open Tasks or Sprints. Move to `### FIND OPEN WORK`

## CREATE SUMMARY

- Get current datetime stamp from the system and compare to initially remembered timestamp. Calculate duration of the process.
- Create a summary report including:
  - Mode executed (Sprint-specific or General)
  - Sprint tasks created (if applicable)
  - Number of tasks completed
  - Number of tasks skipped/failed
  - Total duration
  - Any critical issues encountered
  - Current test status
  - Next recommended action
- Report the result of the review to the user including the duration.


## 작업내용 정리
- 작업이 마무리 되었다면 기존에 존재하던 PROJECT_MANIFEST.md에 작업 사항 반영. 무조건 기존에 있던 PROJECT_MANIFEST.md에 반영 할 것. 새로 생성 금지.
- 리포트에 개선되어야 하는 사항이 리포트 되었다면 simone의 /create_general_task 명령을 활용 하여 일반 테스크로 생성
- 커밋 안된 작업 있다면 작업 내용 커밋하고 마스터에 반영
