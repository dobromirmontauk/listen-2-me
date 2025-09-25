from setuptools import setup, find_packages

setup(
    name="listen2me",
    version="0.1.0",
    description="LLM-powered notetaking & idea organizer app",
    author="",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "pyaudio>=0.2.11",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "google-cloud-speech>=2.16.0",
        "google-auth>=2.10.0",
        "rich>=12.5.0",
        "click>=8.1.0",
        "pydantic>=1.10.0",
        "pyyaml>=6.0.0",
        "pypubsub>=4.0.3",
        "aiohttp>=3.8.0",
    ],
    entry_points={
        "console_scripts": [
            "listen2me=listen2me.main:main",
        ],
    },
)
