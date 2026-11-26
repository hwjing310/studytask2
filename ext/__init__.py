"""CampusEvent 扩展包（实验二 CR-01：年级限定报名）。

设计前提：**不修改 project/ 与 frontend/src/ 下的任何原文件**。
所有扩展通过新增文件 + 运行时组合/注入实现：

- ext.schema      ：新增表与列（students.grade、ext_activity_grade_rules）
- ext.rules       ：年级规则仓储
- ext.services    ：继承原服务，只覆写必要方法（组合而非修改）
- ext.api         ：新增路由，注入原 web 模块的命名空间由 collect_routes 扫描
- ext.pages       ：独立页面（原前端 dist 不动）
- run_ext.py      ：新的启动入口，装配原组件 + 扩展组件
"""

__version__ = "1.0.0"
