#!/usr/bin/env python3
"""
Neo4j Aura Configuration Helper

This script helps you configure your Neo4j Aura connection details
for the ArchiMind application.
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create or update .env file with Neo4j Aura configuration."""
    env_file = Path('.env')
    
    print("🔧 Neo4j Aura Configuration Helper")
    print("=" * 50)
    print()
    print("This script will help you configure your Neo4j Aura connection.")
    print("You can find your connection details in the Neo4j Aura console:")
    print("https://console.neo4j.io")
    print()
    
    # Get connection details from user
    print("Enter your Neo4j Aura connection details:")
    print()
    
    uri = input("Neo4j Aura URI (e.g., neo4j+s://xxxxx.databases.neo4j.io): ").strip()
    if not uri:
        print("❌ URI is required")
        return False
    
    if not uri.startswith('neo4j+s://'):
        print("⚠️  Warning: Neo4j Aura URIs should start with 'neo4j+s://'")
        confirm = input("Continue anyway? (y/N): ").strip().lower()
        if confirm != 'y':
            return False
    
    username = input("Username (usually 'neo4j'): ").strip() or 'neo4j'
    password = input("Password: ").strip()
    if not password:
        print("❌ Password is required")
        return False
    
    # Ask for additional Aura details (optional)
    print()
    print("Additional Aura details (optional, press Enter to skip):")
    database = input("Database name (default: neo4j): ").strip() or 'neo4j'
    instance_id = input("Instance ID (optional): ").strip()
    instance_name = input("Instance name (optional): ").strip()
    
    # Create .env content
    env_content = f"""# Neo4j Aura Configuration
NEO4J_URI={uri}
NEO4J_USER={username}
NEO4J_PASSWORD={password}
NEO4J_DATABASE={database}"""
    
    if instance_id:
        env_content += f"\nAURA_INSTANCEID={instance_id}"
    if instance_name:
        env_content += f"\nAURA_INSTANCENAME={instance_name}"
    
    env_content += """

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
"""
    
    # Write .env file
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print()
        print("✅ Configuration saved to .env file")
        print()
        print("Next steps:")
        print("1. Run: python setup_neo4j.py")
        print("2. Run: python run.py")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def test_connection():
    """Test the Neo4j Aura connection."""
    print("🧪 Testing Neo4j Aura connection...")
    
    try:
        from neo4j_client import Neo4jClient
        client = Neo4jClient()
        
        if client.test_connection():
            print("✅ Connection successful!")
            client.close()
            return True
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Main configuration function."""
    if not create_env_file():
        sys.exit(1)
    
    print("Would you like to test the connection now? (y/N): ", end='')
    test = input().strip().lower()
    
    if test == 'y':
        if test_connection():
            print("🎉 Configuration complete! You can now run the application.")
        else:
            print("❌ Connection test failed. Please check your credentials.")
            sys.exit(1)
    else:
        print("Configuration saved. You can test it later with: python setup_neo4j.py")

if __name__ == "__main__":
    main()