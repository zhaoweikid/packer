## packer介绍 

此项目起源于webpack太多坑，到处都是黑魔法，其实我们只需要一个简单的工具。 
packer只是一个非常简单的用于前端项目开发打包的工具。
目前只支持：
* 极简的语法: 只有 ```<!-- 文件类型:文件名,文件名 -->```
  - 一条表示一个最终的文件。如果文件类型后面有多个文件，是js或css，那么多个文件将会自动合并成一个 packer.bundle.n.js 或者 packer.bundle.n.css
  - 其中文件类型支持: html js css sass image
  - 其中文件名为源目录里面的文件名
  ```例如:
    <!-- html:a.html,b.html --> 表示将 a.html和b.html的内容放到当前位置
    <!-- js:a.js,b.js,c.js --> 表示将 a.js b.js c.js 合并为一个packer.bundle.js并在此位置外部引用packer.bundle.js
    <!-- cs:a.css,b.css,c.css -->  表示将 a.css b.css c.css 合并为一个packer.bundle.css并在此位置外部引用packer.bundle.css
  ```
* 支持sass自动生成css
* 文件自动加md5后缀, 自动写入html文件中
* 自动监控文件变化，产生变化自动生成到目标目录
* 调试用的 http server，默认启动在8000端口，通过 http://127.0.0.1:8000 直接访问页面，调试简单。
 
