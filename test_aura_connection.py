#!/usr/bin/env python3
"""
Test Neo4j Aura Connection

This script tests the connection to Neo4j Aura and provides detailed diagnostics.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Test if environment variables are loaded correctly."""
    print("🔍 Testing Environment Variables")
    print("=" * 40)
    
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER')
    password = os.getenv('NEO4J_PASSWORD')
    database = os.getenv('NEO4J_DATABASE')
    
    print(f"NEO4J_URI: {uri}")
    print(f"NEO4J_USER: {user}")
    print(f"NEO4J_PASSWORD: {'*' * len(password) if password else 'Not set'}")
    print(f"NEO4J_DATABASE: {database}")
    print()
    
    if not uri or not user or not password:
        print("❌ Missing required environment variables")
        return False
    
    if not uri.startswith('neo4j+s://'):
        print("❌ URI should start with 'neo4j+s://' for Aura")
        return False
    
    print("✅ Environment variables look correct")
    return True

def test_network():
    """Test network connectivity."""
    print("🌐 Testing Network Connectivity")
    print("=" * 40)
    
    import socket
    
    uri = os.getenv('NEO4J_URI')
    if not uri:
        print("❌ No URI found")
        return False
    
    # Extract hostname from URI
    hostname = uri.replace('neo4j+s://', '').split(':')[0]
    port = 7687
    
    print(f"Testing connection to: {hostname}:{port}")
    
    try:
        # Try to resolve hostname
        ip = socket.gethostbyname(hostname)
        print(f"✅ Hostname resolved to: {ip}")
        
        # Try to connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            print("✅ Port 7687 is reachable")
            return True
        else:
            print(f"❌ Cannot connect to port 7687 (error code: {result})")
            return False
            
    except socket.gaierror as e:
        print(f"❌ Cannot resolve hostname: {e}")
        return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False

def test_neo4j_connection():
    """Test actual Neo4j connection."""
    print("🔗 Testing Neo4j Connection")
    print("=" * 40)
    
    try:
        from neo4j import GraphDatabase
        
        uri = os.getenv('NEO4J_URI')
        user = os.getenv('NEO4J_USER')
        password = os.getenv('NEO4J_PASSWORD')
        database = os.getenv('NEO4J_DATABASE', 'neo4j')
        
        print(f"Connecting to: {uri}")
        print(f"Database: {database}")
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session(database=database) as session:
            result = session.run("RETURN 1 as test")
            test_value = result.single()['test']
            
            if test_value == 1:
                print("✅ Neo4j connection successful!")
                return True
            else:
                print("❌ Unexpected result from Neo4j")
                return False
                
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")
        return False
    finally:
        try:
            driver.close()
        except:
            pass

def main():
    """Main test function."""
    print("🧪 Neo4j Aura Connection Test")
    print("=" * 50)
    print()
    
    # Test 1: Environment variables
    if not test_environment():
        print("\n❌ Environment test failed. Please check your .env file.")
        sys.exit(1)
    
    print()
    
    # Test 2: Network connectivity
    if not test_network():
        print("\n❌ Network test failed. Please check:")
        print("1. Your internet connection")
        print("2. Your Aura instance is running")
        print("3. The instance ID is correct")
        sys.exit(1)
    
    print()
    
    # Test 3: Neo4j connection
    if not test_neo4j_connection():
        print("\n❌ Neo4j connection test failed. Please check:")
        print("1. Your credentials are correct")
        print("2. Your Aura instance allows connections")
        print("3. The database name is correct")
        sys.exit(1)
    
    print("\n🎉 All tests passed! Your Neo4j Aura connection is working.")

if __name__ == "__main__":
    main()