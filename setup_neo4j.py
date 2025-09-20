#!/usr/bin/env python3
"""
Neo4j Database Setup Script for ArchiMind

This script sets up the necessary constraints, indexes, and vector index
for the ArchiMind application in Neo4j.
"""

import os
import sys
from neo4j_client import Neo4jClient

def main():
    """Set up Neo4j database schema and indexes."""
    print("Setting up Neo4j Aura database for ArchiMind...")
    
    try:
        # Initialize Neo4j client
        client = Neo4jClient()
        
        # Test connection
        print("Testing Neo4j Aura connection...")
        if not client.test_connection():
            print("❌ Failed to connect to Neo4j Aura")
            print("Please ensure your Aura instance is running and check your connection settings.")
            print("Your NEO4J_URI should start with 'neo4j+s://' for Aura.")
            return False
        
        print("✅ Connected to Neo4j Aura successfully")
        
        # Initialize schema
        print("Creating database schema and indexes...")
        client.initialize_schema()
        
        print("✅ Database schema initialized successfully")
        
        # Test vector search capability
        print("Testing vector search capability...")
        try:
            # This will fail if the vector index doesn't exist, which is expected
            results = client.search_similar_code("test query", limit=1)
            print("✅ Vector search is working")
        except Exception as e:
            if "vector index" in str(e).lower():
                print("⚠️  Vector index not found. Please run the following Cypher query in Neo4j Browser:")
                print()
                print("CREATE VECTOR INDEX code_embeddings IF NOT EXISTS")
                print("FOR (c:CodeChunk) ON (c.embedding)")
                print("OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}};")
                print()
                print("Then run this script again to verify the setup.")
                return False
            else:
                print(f"❌ Vector search test failed: {e}")
                return False
        
        print("✅ Neo4j setup completed successfully!")
        print()
        print("You can now start the ArchiMind application with:")
        print("  python app.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Ensure your Neo4j Aura instance is running")
        print("2. Check your connection settings in .env file")
        print("3. Verify your Aura instance URI starts with 'neo4j+s://'")
        print("4. Check if your Aura instance allows the required APOC procedures")
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)