# Latergram
![img](latergom.png)<br>
Real instagram, better and secure

## PLEASE CHECK THE BRANCH LADS

### Information
Structure: app-server, reverse-proxy, snort3-build<br>
For credentials, refer to the credential-master for comprehensive list of credentials. <br><br>
IMPORTANT: take note of the branch that you are working on. If the current branch has not been merged into production (main), it will remain. Naming scheme of development branch will follow the format: dev-release-*.*.* 

There will be 2 different copies of implementation to cover Code Integration (CI). CI will be using the simplified versions of nginx.conf, docker-compose.yml so the GitHub Actions can carry out lightweight and functional checks.

#### app-server:
Flask web server with static resources. Here is 2/3 of the web application stack, main development likely to be done here. If any sensitive data exposure that shouldn't be in plaintext, raise in the group
