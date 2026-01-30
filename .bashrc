# ~/.bashrc: executed by bash(1) for non-login shells.

# Note: PS1 and umask are already set in /etc/profile. You should not
# need this unless you want different defaults for root.
# PS1='${debian_chroot:+($debian_chroot)}\h:\w\$ '
# umask 022

# You may uncomment the following lines if you want `ls' to be colorized:
export LS_OPTIONS='--color=auto'
eval "`dircolors`"
alias ls='ls $LS_OPTIONS'
alias grep='grep --color=auto'
alias diff='diff --color=auto'
alias ll='ls $LS_OPTIONS -l'
alias l='ls $LS_OPTIONS -lA'
alias c='clear'

# 彩色提示符：绿色用户名@主机名 + 蓝色路径 + 号
PS1='\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]# '

# Some more alias to avoid making mistakes:
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'
export XDG_RUNTIME_DIR=/run/user/$(id -u)

####### 发现下载python 包啥的，速度慢，就设置下代理
export https_proxy=http://sys-proxy-rd-relay.byted.org:3128 
export http_proxy=http://sys-proxy-rd-relay.byted.org:3128
export no_proxy='.byted.org'

export PATH=$PATH:~/.vscode-server/cli/servers/Stable-7d842fb85a0275a4a8e4d7e040d2625abbf7f084/server/bin/remote-cli/