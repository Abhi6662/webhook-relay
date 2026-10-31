from setuptools import setup, find_packages

setup(
    name="webhook-relay",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.32.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0.0", "httpx>=0.27.0"],
    },
    python_requires=">=3.10",
)
