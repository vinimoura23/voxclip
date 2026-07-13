from setuptools import setup, find_packages

setup(
    name="voxclip",
    version="0.1.0",
    description="Voice-to-Clipboard for Hyprland/Wayland",
    author="VoxClip",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "faster-whisper>=1.0.0",
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
        "pycairo>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "voxclip=voxclip.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Environment :: Wayland",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
    ],
)
