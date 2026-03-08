# Download and build libiio
sudo apt install libxml2 libxml2-dev bison flex cmake git libaio-dev libboost-all-dev

# Download and build libad9361-iio
cd ~
git clone https://github.com/analogdevicesinc/libad9361-iio.git
cd libad9361-iio
mkdir build
cd build
cmake .. -DPYTHON_BINDINGS=ON
make 
sudo make install
cd ../..
