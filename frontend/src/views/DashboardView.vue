<template>
  <div class="page">
    <div class="page-title">
      <div>
        <h1>概览</h1>
        <p>查看当前任务、测试批次和第一阶段闭环状态。</p>
      </div>
      <RouterLink class="button primary" to="/tasks/new">新建任务</RouterLink>
    </div>

    <div class="metrics">
      <div class="metric">
        <span>任务数</span>
        <strong>{{ summary.task_count ?? 0 }}</strong>
      </div>
      <div class="metric">
        <span>批次数</span>
        <strong>{{ summary.batch_count ?? 0 }}</strong>
      </div>
      <div class="metric">
        <span>完成批次</span>
        <strong>{{ summary.completed_batch_count ?? 0 }}</strong>
      </div>
    </div>

    <SectionPanel title="最近任务" description="从任务进入配置、运行和结果查看。">
      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>状态</th>
            <th>创建时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in summary.latest_tasks || []" :key="task.id">
            <td>{{ task.name }}</td>
            <td>联网搜索型</td>
            <td><StatusBadge :status="task.status" /></td>
            <td>{{ formatTime(task.created_at) }}</td>
            <td><RouterLink :to="`/tasks/${task.id}`">查看</RouterLink></td>
          </tr>
        </tbody>
      </table>
    </SectionPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import SectionPanel from '../components/SectionPanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { getSummary } from '../api/platform'
import { formatTime } from '../utils/format'

const summary = ref<any>({})

onMounted(async () => {
  summary.value = await getSummary()
})
</script>
