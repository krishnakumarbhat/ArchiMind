#!/usr/bin/env python3
"""
ArchiMind Setup Test Script

This script tests the ArchiMind setup by running a simple repository analysis
on a small public repository to verify all components are working correctly.
"""

import sys
import time
from agents import ArchiMindWorkflow

def test_repository_analysis():
    """Test repository analysis with a small public repository."""
    print("🧪 Testing ArchiMind with a small repository...")
    print()
    
    # Use a small, well-known repository for testing
    test_repo = "https://github.com/octocat/Hello-World"
    
    try:
        print(f"📁 Analyzing repository: {test_repo}")
        print("⏳ This may take a few minutes...")
        print()
        
        # Initialize workflow
        workflow = ArchiMindWorkflow()
        
        # Run analysis
        start_time = time.time()
        result = workflow.run(test_repo)
        end_time = time.time()
        
        if result.get('error'):
            print(f"❌ Analysis failed: {result['error']}")
            return False
        
        # Check results
        hld = result.get('hld', {})
        lld = result.get('lld', {})
        readme = result.get('readme', '')
        
        print("✅ Analysis completed successfully!")
        print(f"⏱️  Processing time: {end_time - start_time:.2f} seconds")
        print()
        
        # Display results summary
        print("📊 Results Summary:")
        print(f"  • README length: {len(readme)} characters")
        print(f"  • HLD nodes: {len(hld.get('nodes', []))}")
        print(f"  • HLD edges: {len(hld.get('edges', []))}")
        print(f"  • LLD nodes: {len(lld.get('nodes', []))}")
        print(f"  • LLD edges: {len(lld.get('edges', []))}")
        print()
        
        if readme:
            print("📖 README Preview:")
            preview = readme[:200] + "..." if len(readme) > 200 else readme
            print(f"  {preview}")
            print()
        
        print("🎉 All tests passed! ArchiMind is ready to use.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Ensure all services are running (Neo4j Aura, Ollama)")
        print("2. Check your .env configuration")
        print("3. Verify internet connection for repository access")
        print("4. Run: python configure_aura.py to set up Aura credentials")
        return False

def main():
    """Main test function."""
    print("🔍 ArchiMind Setup Test")
    print("=" * 50)
    print()
    
    success = test_repository_analysis()
    
    if success:
        print()
        print("🚀 You can now start the application with:")
        print("  python run.py")
        print("  or")
        print("  python app.py")
    else:
        print()
        print("❌ Setup test failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()