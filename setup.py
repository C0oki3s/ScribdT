from setuptools import setup, find_packages

setup(
    name='ScribdT',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'argparse',
        'beautifulsoup4',
        'requests',
        'spacy',
        'presidio_analyzer',
    ],
entry_points={
    'console_scripts': [
        'ScribdT = scribd_tool.core:main',
    ],
}

)
