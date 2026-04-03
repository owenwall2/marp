# Download and build libiio
apt update
apt install -y libxml2 libxml2-dev bison flex cmake git libaio-dev libboost-all-dev swig libavahi-client-dev libavahi-common-dev

# Blank Docker install requirment
apt install -y python3-pip python3-setuptools
apt install -y liborc-0.4-0 liborc-0.4-dev
apt install -y iproute2 inetutils-ping nano
apt install -y libiio-utils

apt install -y git cmake build-essential libxml2-dev libusb-1.0-0-dev python3-dev pkg-config

apt install -y swig pkg-config
apt install -y doxygen



cd ~
git clone --depth 1 --branch v0.26 https://github.com/analogdevicesinc/libiio.git
cd libiio
mkdir build && cd build

cmake .. -DCMAKE_BUILD_TYPE=Release  -DCMAKE_INSTALL_PREFIX=/usr #-DPYTHON_BINDINGS=ON

make -j$(nproc)
make install
ldconfig

pip3 install gevent flask flask-socketio pyzmq sphinx

# Download and build libad9361-iio
cd ~
git clone https://github.com/analogdevicesinc/libad9361-iio.git
cd libad9361-iio
mkdir build
cd build
cmake .. -DPYTHON_BINDINGS=ON -DWITH_DOC=ON -DSPHINX_EXECUTABLE=/bin/true
make 
make install
cd ../..


