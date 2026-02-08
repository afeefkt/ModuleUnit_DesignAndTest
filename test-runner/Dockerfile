FROM ubuntu:22.04

# Install build tools and CppUTest
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    make \
    cmake \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CppUTest from source (latest version)
RUN cd /tmp && \
    git clone --depth 1 https://github.com/cpputest/cpputest.git && \
    cd cpputest && \
    rm -rf build && mkdir build && cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local && \
    make -j$(nproc) && \
    make install && \
    cd / && rm -rf /tmp/cpputest

# Create working directory
WORKDIR /tests

# Default command
CMD ["/bin/bash", "-c", "echo 'CppUTest Test Runner Ready' && tail -f /dev/null"]
