from setuptools import setup, find_packages

setup(
    name="listen2me",
    version="0.1.0",
    description="LLM-powered notetaking & idea organizer app",
    author="Listen2Me Team",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "pyaudio>=0.2.11",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "rich>=12.5.0",
        "click>=8.1.0",
        "pydantic>=1.10.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.1.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "isort>=5.10.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "listen2me=listen2me.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)