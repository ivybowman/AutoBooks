LATEST_VERSION=$(curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE)
echo "Updating Packages"
sudo apt-get update
echo "Installing Prerequisites"
sudo apt-get install -y unzip ffmpeg git python3-pip
wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$LATEST_VERSION/chromedriver_linux64.zip
echo "Installing ChromeDriver"
sudo unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/
echo "Finished"