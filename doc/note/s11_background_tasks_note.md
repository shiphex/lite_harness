# background_tasks


# 1. 为什么需要让工具执行在后台执行？

- 部分使用工具的任务执行实践较长，需要在后台执行，以避免阻塞主进程。
- 这些任务不会因为时序问题影响后续任务的执行

# 2. 如何实现工具执行在后台？

- should_run_background 判断函数是否应该在后台运行任务。
- start_background_task 启动后台任务。
- inject_background_results 向消息列表中注入后台任务结果。









