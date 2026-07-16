<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">AE</div>
        <div>
          <strong>Agent Eval</strong>
          <span>联网搜索配置测试</span>
        </div>
      </div>
      <nav>
        <RouterLink to="/">概览</RouterLink>
        <RouterLink to="/tasks">测试任务</RouterLink>
        <RouterLink to="/tasks/pipeline">任务流水线</RouterLink>
        <RouterLink to="/tasks/new">创建任务</RouterLink>
        <RouterLink to="/models">模型库</RouterLink>
      </nav>
    </aside>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>
