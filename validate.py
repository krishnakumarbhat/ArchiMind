#!/usr/bin/env python3
"""
ArchiMind Validation Script
Checks system dependencies, configuration, and basic functionality.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Tuple, List


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


class ValidationCheck:
    """Base class for validation checks."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
    
    def run(self) -> Tuple[bool, str]:
        """Run the validation check. Returns (success, message)."""
        raise NotImplementedError
    
    def print_result(self):
        """Print the check result with colored output."""
        symbol = f"{Colors.GREEN}✓{Colors.NC}" if self.passed else f"{Colors.RED}✗{Colors.NC}"
        print(f"  {symbol} {self.name}: {self.message}")


class PythonVersionCheck(ValidationCheck):
    """Check Python version."""
    
    def run(self) -> Tuple[bool, str]:
        version = sys.version_info
        self.passed = version.major == 3 and version.minor >= 11
        self.message = f"{version.major}.{version.minor}.{version.micro}"
        if not self.passed:
            self.message += " (3.11+ required)"
        return self.passed, self.message


class DependencyCheck(ValidationCheck):
    """Check if a command-line tool is installed."""
    
    def __init__(self, name: str, command: str):
        super().__init__(name)
        self.command = command
    
    def run(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                [self.command, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            self.passed = result.returncode == 0
            self.message = "Installed" if self.passed else "Not found"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.passed = False
            self.message = "Not found"
        return self.passed, self.message


class PythonPackageCheck(ValidationCheck):
    """Check if a Python package is installed."""
    
    def __init__(self, package_name: str):
        super().__init__(f"Python package: {package_name}")
        self.package_name = package_name
    
    def run(self) -> Tuple[bool, str]:
        try:
            __import__(self.package_name)
            self.passed = True
            self.message = "Installed"
        except ImportError:
            self.passed = False
            self.message = "Not installed"
        return self.passed, self.message


class FileExistsCheck(ValidationCheck):
    """Check if a file exists."""
    
    def __init__(self, filepath: str, required: bool = True):
        super().__init__(f"File: {filepath}")
        self.filepath = filepath
        self.required = required
    
    def run(self) -> Tuple[bool, str]:
        self.passed = Path(self.filepath).exists()
        self.message = "Found" if self.passed else "Not found"
        if not self.passed and not self.required:
            self.message += " (optional)"
        return self.passed, self.message


class EnvironmentVariableCheck(ValidationCheck):
    """Check if an environment variable is set."""
    
    def __init__(self, var_name: str, required: bool = True):
        super().__init__(f"Environment: {var_name}")
        self.var_name = var_name
        self.required = required
    
    def run(self) -> Tuple[bool, str]:
        value = os.getenv(self.var_name)
        self.passed = value is not None and value != ""
        
        if self.passed:
            # Mask sensitive values
            if 'KEY' in self.var_name or 'PASSWORD' in self.var_name:
                masked = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '***'
                self.message = f"Set ({masked})"
            else:
                self.message = f"Set ({value})"
        else:
            self.message = "Not set"
            if not self.required:
                self.message += " (optional)"
        
        return self.passed, self.message


class DatabaseConnectionCheck(ValidationCheck):
    """Check database connectivity."""
    
    def run(self) -> Tuple[bool, str]:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            from app import ArchiMindApplication
            app_instance = ArchiMindApplication()
            
            with app_instance.app.app_context():
                from app import db
                # Try to connect
                db.engine.connect()
            
            self.passed = True
            self.message = "Connected successfully"
        except Exception as e:
            self.passed = False
            self.message = f"Connection failed: {str(e)[:50]}"
        
        return self.passed, self.message


class OllamaServiceCheck(ValidationCheck):
    """Check if Ollama service is running."""
    
    def run(self) -> Tuple[bool, str]:
        try:
            import requests
            response = requests.get('http://localhost:11434/api/tags', timeout=2)
            self.passed = response.status_code == 200
            self.message = "Running" if self.passed else "Not responding"
        except Exception:
            self.passed = False
            self.message = "Not running or not accessible"
        
        return self.passed, self.message


def print_header():
    """Print validation header."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}  ArchiMind Validation Script{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}\n")


def print_section(title: str):
    """Print section header."""
    print(f"\n{Colors.YELLOW}{title}{Colors.NC}")


def run_validation() -> Tuple[int, int]:
    """Run all validation checks. Returns (passed, total) counts."""
    checks: List[ValidationCheck] = []
    
    # System checks
    print_section("System Dependencies")
    checks.extend([
        PythonVersionCheck("Python version"),
        DependencyCheck("PostgreSQL", "psql"),
        DependencyCheck("Git", "git"),
        DependencyCheck("Ollama", "ollama"),
    ])
    
    # Python packages
    print_section("Python Packages")
    packages = ['flask', 'sqlalchemy', 'chromadb', 'ollama', 'git', 'google.generativeai']
    checks.extend([PythonPackageCheck(pkg) for pkg in packages])
    
    # Files
    print_section("Project Files")
    checks.extend([
        FileExistsCheck("app.py"),
        FileExistsCheck("services.py"),
        FileExistsCheck("worker.py"),
        FileExistsCheck("config.py"),
        FileExistsCheck("requirements.txt"),
        FileExistsCheck(".env"),
        FileExistsCheck("templates/index.html"),
        FileExistsCheck("templates/doc.html"),
    ])
    
    # Environment variables
    print_section("Environment Configuration")
    checks.extend([
        EnvironmentVariableCheck("GEMINI_API_KEY"),
        EnvironmentVariableCheck("DATABASE_URL"),
        EnvironmentVariableCheck("SECRET_KEY"),
    ])
    
    # Service checks
    print_section("Service Connectivity")
    checks.extend([
        DatabaseConnectionCheck("PostgreSQL Database"),
        OllamaServiceCheck("Ollama Service"),
    ])
    
    # Run all checks
    passed = 0
    total = 0
    
    for check in checks:
        check.run()
        check.print_result()
        if check.passed:
            passed += 1
        total += 1
    
    return passed, total


def print_summary(passed: int, total: int):
    """Print validation summary."""
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"\n  Results: {passed}/{total} checks passed ({percentage:.1f}%)\n")
    
    if passed == total:
        print(f"  {Colors.GREEN}✓ All checks passed! ArchiMind is ready to run.{Colors.NC}")
        print(f"\n  Start the application with: {Colors.BLUE}python app.py{Colors.NC}")
    elif passed >= total * 0.8:
        print(f"  {Colors.YELLOW}! Most checks passed. Review warnings above.{Colors.NC}")
        print(f"\n  You may be able to run ArchiMind with limited functionality.")
    else:
        print(f"  {Colors.RED}✗ Several checks failed. Please fix the issues above.{Colors.NC}")
        print(f"\n  Refer to README.md for setup instructions.")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}\n")


def print_recommendations():
    """Print setup recommendations."""
    print(f"\n{Colors.YELLOW}Setup Recommendations:{Colors.NC}\n")
    
    recommendations = [
        "1. Ensure PostgreSQL is running: sudo systemctl status postgresql",
        "2. Start Ollama service: ollama serve",
        "3. Download embedding model: ollama pull nomic-embed-text",
        "4. Set environment variables in .env file",
        "5. Run tests: pytest tests/ -v",
        "6. Check logs in data/ directory",
    ]
    
    for rec in recommendations:
        print(f"  {rec}")
    
    print()


def main():
    """Main validation function."""
    print_header()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(f"{Colors.GREEN}✓ Loaded environment variables from .env{Colors.NC}\n")
    except ImportError:
        print(f"{Colors.YELLOW}! python-dotenv not installed, skipping .env loading{Colors.NC}\n")
    except Exception as e:
        print(f"{Colors.YELLOW}! Could not load .env file: {e}{Colors.NC}\n")
    
    # Run validation
    passed, total = run_validation()
    
    # Print summary
    print_summary(passed, total)
    
    # Print recommendations if needed
    if passed < total:
        print_recommendations()
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
