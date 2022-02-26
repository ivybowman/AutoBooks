LATEST_VERSION=$(curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE)
echo "Updating Packages"
sudo apt-get update
echo "Installing Prerequisites"
sudo apt-get install -y unzip ffmpeg git 
wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$LATEST_VERSION/chromedriver_linux64.zip
echo "Installing Chrome"
sudo unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
echo "Finished"