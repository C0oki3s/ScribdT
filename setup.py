from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess
import sys
import platform
import os
import time

class CustomInstallCommand(install):
    """Customized setuptools install command to download spaCy model."""
    def run(self):
        install.run(self) 
        for attempt in range(3):
            try:
                print(f"\nDownloading spaCy model 'en_core_web_lg' (attempt {attempt + 1}/3)...")
                cmd = [sys.executable, "-m", "spacy", "download", "en_core_web_lg"]
             
                if platform.system() == "Linux":
                    try:
                       
                        with open("/etc/python3/debian_config", "r") as f:
                            if "externally-managed" in f.read().lower():
                                cmd.append("--break-system-packages")
                    except FileNotFoundError:
                        pass  
                subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
                print("Successfully downloaded 'en_core_web_lg'.")
              
                import spacy
                spacy.load("en_core_web_lg")
                print("Verified: 'en_core_web_lg' model is installed correctly.")
                break
            except (subprocess.CalledProcessError, ImportError, OSError) as e:
                print(f"\nFailed to download or verify spaCy model: {e}")
                time.sleep(2) 
                if attempt == 2:
                    print("All attempts failed. Please run manually after installation:")
                    print("  python -m spacy download en_core_web_lg")
                    print("Continuing installation without verifying the model.")

setup(
    name='ScribdT',
    version='0.2',
    packages=find_packages(),
    install_requires=[
        'beautifulsoup4>=4.9.0',
        'requests>=2.25.0',
        'spacy>=3.0.0,<4.0.0', 
        'presidio-analyzer>=2.2.34',
    ],
    entry_points={
        'console_scripts': [
            'ScribdT = scribd_tool.core:main',
        ],
    },
    cmdclass={
        'install': CustomInstallCommand,
    },
    python_requires='>=3.7',  # Explicitly support Python 3.12
    description='A tool for processing Scribd data',
    long_description=open('README.md', encoding='utf-8').read() if os.path.exists('README.md') else '',
    long_description_content_type='text/markdown',
    license='MIT',
)