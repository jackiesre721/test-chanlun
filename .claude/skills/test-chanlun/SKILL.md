```markdown
# test-chanlun Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `test-chanlun` TypeScript codebase. It covers file naming, import/export styles, commit message conventions, and testing patterns. By following these guidelines, contributors can maintain consistency and quality across the project.

## Coding Conventions

### File Naming
- Use **kebab-case** for all file names.
  - Example:  
    ```text
    my-component.ts
    user-service.test.ts
    ```

### Import Style
- Use **alias imports** for modules.
  - Example:
    ```typescript
    import { fetchData } from '@utils/network';
    ```

### Export Style
- Use **named exports** instead of default exports.
  - Example:
    ```typescript
    // In utils.ts
    export function calculateSum(a: number, b: number): number {
      return a + b;
    }

    // In another file
    import { calculateSum } from '@utils/utils';
    ```

### Commit Messages
- Use **conventional commits** with the `feat` prefix for new features.
  - Example:
    ```
    feat: add user authentication module
    ```
- Keep commit messages concise (average ~80 characters).

## Workflows

_No automated workflows detected in this repository._

## Testing Patterns

- Test files use the pattern `*.test.*`.
  - Example:  
    ```text
    user-service.test.ts
    ```
- The testing framework is **unknown**, but tests are colocated with source files or in the same directory.

- Example test file structure:
  ```typescript
  // user-service.test.ts
  import { getUser } from '@services/user-service';

  describe('getUser', () => {
    it('should return user data for valid ID', () => {
      // test implementation
    });
  });
  ```

## Commands
| Command | Purpose |
|---------|---------|
| /test   | Run all tests in the repository |
| /lint   | Lint the codebase according to conventions |
| /commit | Generate a conventional commit message |
```
