# Gemini CLI Editing Conventions

This document defines the mandatory, enforceable editing workflow for the Gemini CLI within this repository. Adherence to this protocol is required to ensure patch stability and prevent editing failures.

**All edits in this repository MUST follow the context-anchored edit workflow.**

---

## 1. Golden Editing Rules

1.  **Block-Level Cohesion**: All edits must operate on logical blocks of code (e.g., a whole function, a class, a complete `if/else` block), not on single, isolated lines.
2.  **Context is King**: A change must be anchored by sufficient, unique surrounding context to guarantee its target location is unambiguous.
3.  **Verify, Then Act**: Never attempt a modification without first reading the file to get the latest version of the target code block.
4.  **Tests are Synchronized**: No logic change is complete until the corresponding unit tests are updated to reflect the new behavior.
5.  **Logging is Sacred**: The `events.jsonl` file and any other structured logs are immutable records. They must never be manually edited or corrupted.

---

## 2. Standard Patch Pipeline

Every logical change to a single file MUST follow this exact sequence:

1.  **`read_file(file_path)`**: Read the full, current content of the file to be modified.

2.  **Identify Target Block**: From the content read in Step 1, identify the entire logical block of code (e.g., the function `def my_func(...): ...`) that needs to be changed. This block MUST include at least 3 lines of preceding and succeeding context that will not be changed, to serve as a unique anchor.

3.  **`replace(old_string, new_string)`**:
    *   **`old_string`**: The *exact, literal, character-for-character* text of the entire target block identified in Step 2, including the unchanged context anchors.
    *   **`new_string`**: The new version of the entire block, including the identical, unchanged context anchors.

4.  **Prohibition**: The use of single-line, exact-string replacement is strictly forbidden. All replacements must be context-anchored blocks.

---

## 3. Multi-File Editing Rules

- When a single logical change affects multiple files (e.g., a function rename and its usage sites), modifications must be performed sequentially.
- Complete the full "Standard Patch Pipeline" for the first file and verify its success before beginning the pipeline for the next file.

---

## 4. Failure Recovery Protocol

If a `replace` operation fails for any reason (e.g., "0 occurrences found"), the recovery procedure is non-negotiable:

1.  **Halt `replace` Attempts**: Do not retry the `replace` command.
2.  **Re-read the File**: Execute `read_file(file_path)` again to ensure you have the absolute latest file content.
3.  **Full Rewrite**: Generate the *entire file content* in memory, applying the desired logical change to the relevant block.
4.  **`write_file(file_path, full_content)`**: Use the `write_file` tool to completely overwrite the file with the newly generated full content. This is the terminal step for a failed `replace`.

---

## 5. Unit Test Synchronization

- If a file `aios/module/logic.py` is modified, the corresponding test file `aios/tests/test_logic.py` MUST be immediately read, analyzed, and updated in a subsequent, separate step to reflect the changes.
- Test files must be successfully run after changes are made to either the logic or the test itself.
- If a logic change is intended to fix a failing test, the test MUST be run again after the patch to prove the fix.
