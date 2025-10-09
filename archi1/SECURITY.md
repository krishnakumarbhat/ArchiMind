# Security Notice

## 🔒 Important: Keep Your Credentials Safe

**NEVER commit your `.env` file or any files containing sensitive information to version control!**

### What to Protect

- Neo4j Aura connection details (URI, username, password)
- Any API keys or tokens
- Database credentials
- Any other sensitive configuration

### Files to Never Commit

- `.env` (contains your Aura credentials)
- `.env.local`
- `.env.production`
- Any files with actual credentials instead of placeholders

### Safe Practices

1. **Use the configuration helper**:
   ```bash
   python configure_aura.py
   ```

2. **Check your .gitignore**:
   - Ensure `.env` is listed in `.gitignore`
   - Verify sensitive files are excluded

3. **Use placeholder values in documentation**:
   - Example: `NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io`
   - Never use real credentials in README or example files

4. **Environment-specific configuration**:
   - Use different `.env` files for different environments
   - Never share production credentials

### If You Accidentally Commit Credentials

1. **Immediately rotate your credentials** in Neo4j Aura console
2. **Remove the sensitive data** from your repository history
3. **Update your .gitignore** to prevent future accidents
4. **Notify your team** if working in a shared repository

### Quick Check

Before committing, run:
```bash
git status
```

Make sure no `.env` files or files with real credentials are listed.

---

**Remember**: Security is everyone's responsibility. When in doubt, ask before committing sensitive information.