## EC2 Template Setup
This is the code repository to setup the EC2 template using  AWS cloudformation

To create the stack run  <b> python DeployEstateFromLocal.py </b></br>
Creation of the stack will create and download the pem key in the PEM_KEYS folder </br>
to ssh into the node run the command <b> ssh -i PEM_KEYS/KeyMaterial.pem ec2-user@<Public IP> </b>

