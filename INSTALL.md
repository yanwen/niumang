#所需环境
* python2.5+
* celery
* tornado
* daemon for python
* nginx(可选)

# 安装环境
* celery 参见：http://www.celeryproject.org/install/ , http://ask.github.com/celery/getting-started/broker-installation.html
* daemon: `pip install daemon`
* tornado 参见：http://www.tornadoweb.org

# 安装牛芒
* 执行 `cp config.example.py config.py` 生成配置文件
* 编辑 config.py 配置参数
* 开启 celery
* 执行 `python website.py --debug` 开启牛芒, 如果后台运行执行 `python website.py`
* 用浏览器访问 http://localhost:8800/setup 安装数据库
* 访问 http://localhost:8800 搬运视频

# 配置nginx
如果外部访问建议使用nginx,配置参见 nginx.example.conf 并且 使用 server.sh 运行牛芒
* `./server.sh start 9001` 开启
* `./server.sh stop 9001` 停止
* `./server.sh restart 9001` 重启
