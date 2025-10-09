#!/usr/bin/env python3
"""
Setup .env file from secre.txt

This script reads your secre.txt file and creates a proper .env file
with the correct environment variable names.
"""

import os
from pathlib import Path

def setup_env_from_secrets():
    """Create .env file from secre.txt"""
    secrets_file = Path('secre.txt')
    env_file = Path('.env')
    
    if not secrets_file.exists():
        print("❌ secre.txt file not found")
        print("Please make sure your secrets file is named 'secre.txt'")
        return False
    
    print("🔧 Setting up .env file from secre.txt...")
    
    try:
        # Read secrets file
        with open(secrets_file, 'r') as f:
            lines = f.readlines()
        
        # Parse secrets
        secrets = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                secrets[key.strip()] = value.strip()
        
        # Create .env content with correct variable names
        env_content = f"""# Neo4j Aura Configuration
NEO4J_URI={secrets.get('NEO4J_URI', '')}
NEO4J_USER={secrets.get('NEO4J_USERNAME', '')}
NEO4J_PASSWORD={secrets.get('NEO4J_PASSWORD', '')}
NEO4J_DATABASE={secrets.get('NEO4J_DATABASE', 'neo4j')}"""
        
        # Add optional Aura fields
        if 'AURA_INSTANCEID' in secrets:
            env_content += f"\nAURA_INSTANCEID={secrets['AURA_INSTANCEID']}"
        if 'AURA_INSTANCENAME' in secrets:
            env_content += f"\nAURA_INSTANCENAME={secrets['AURA_INSTANCENAME']}"
        
        env_content += """

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
"""
        
        # Write .env file
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print("✅ .env file created successfully!")
        print()
        print("Next steps:")
        print("1. Run: python setup_neo4j.py")
        print("2. Run: python run.py")
        print()
        print("⚠️  Remember: secre.txt is now in .gitignore and won't be committed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False

def main():
    """Main function"""
    print("🔐 ArchiMind Environment Setup")
    print("=" * 40)
    print()
    
    if setup_env_from_secrets():
        print("🎉 Setup complete!")
    else:
        print("❌ Setup failed. Please check the error messages above.")

if __name__ == "__main__":
    main()