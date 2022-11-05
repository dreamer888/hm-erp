
[![Build Status](http://ci.osbzr.com/api/badges/GoodERPJeff/gooderp/status.svg)](http://ci.osbzr.com/GoodERPJeff/gooderp)


开发环境准备
-------------
0.你能看到这个指南证明你已经在项目里了。

1.点击右上角的【派生】按钮，会创建一个你的项目 http://osbzr.com/你的名字/gooderp

2.clone到本地

    git clone http://osbzr.com/你的名字/gooderp

    
3.切换到gooderp项目目录

    cd gooderp/
    
4.增加远程分支（也就是osbzr的分支）名为osbzr到你本地。

    git remote add osbzr http://osbzr.com/GoodERPJeff/gooderp

    
环境就准备好了


把远程分支的修改合并到自己的分支
----------------------------
1.把对方的代码拉到你本地。

    git fetch osbzr

2.合并对方代码

    git merge osbzr/master

3.最新的代码推送到你的github上。

    git push origin master
    
当本地代码写好要提交到主干项目
-------------------------------
1.添加要提交的目录
    
    git add .
    
2.提交更新

    git commit -m"本次修改的描述"
    
3.推送到github

    git push
    
4.在你的项目 http://osbzr.com/你的名字/gooderp 上点击灰色的【创建合并请求】按钮