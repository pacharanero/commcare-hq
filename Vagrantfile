# -*- mode: ruby -*-
# vi: set ft=ruby :

unless Vagrant.has_plugin?("vagrant-docker-compose")
  system("vagrant plugin install vagrant-docker-compose")
  puts "Dependencies installed, please try the command again."
  exit
end

Vagrant.configure("2") do |config|
  # I am using bento/ubuntu because of a bug in ubuntu/xenial64
  # info: https://bugs.launchpad.net/cloud-images/+bug/1569237
  config.vm.box = "bento/ubuntu-16.04"
  config.vm.box_check_update = true

  ## PORT FORWARDING SETTINGS
  # the 'autocorrect' flag corrects any port clashes on your local machine
  # (but can introduce inconsistency about on which port a given service is located)
  # EDS => normal port 80 web left forwarded, but changed from Vagrant's
  # default of 8080 to something else (so as not to clash with Tomcat)
  config.vm.network "forwarded_port", guest: 80, host: 80, host_ip: "127.0.0.1", auto_correct: true
  config.vm.network "forwarded_port", guest: 8000, host: 8000, host_ip: "127.0.0.1", auto_correct: true

  
  # config.vm.network "private_network", ip: "192.168.33.10"

  # config.vm.network "public_network"

  config.vm.synced_folder ".", "/vagrant"

  config.vm.provider "virtualbox" do |vb|
    # Display the VirtualBox GUI when booting the machine
    # vb.gui = true
    # Customize the amount of memory on the VM:
    vb.memory = "4096"
  end

  ## PROVISIONING

  # OSupdates
  config.vm.provision :shell, inline: "sudo apt-get update"
  config.vm.provision :shell, inline: "sudo apt-get upgrade -y"
  config.vm.provision :shell, inline: "sudo apt-get -y autoremove"

  # install docker
  config.vm.provision :docker, run: "always"

  # install docker-compose
  config.vm.provision :docker_compose, yml: "/vagrant/docker-compose.yml", rebuild: true, run: "always"
end
