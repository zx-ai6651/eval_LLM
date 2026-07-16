<template>
  <div class="page narrow">
    <div class="page-title">
      <div>
        <h1>创建任务</h1>
        <p>第一阶段固定为联网搜索型任务，创建后会自动加载默认评测权重。</p>
      </div>
    </div>

    <SectionPanel title="任务信息">
      <form class="form" @submit.prevent="submit">
        <label>
          <span>任务名称</span>
          <input v-model="form.name" required placeholder="例如：企业公开信息背调测试" />
        </label>
        <label>
          <span>任务描述</span>
          <textarea v-model="form.description" rows="4" placeholder="描述需要 Agent 完成的联网搜索任务" />
        </label>
        <label>
          <span>任务背景</span>
          <textarea v-model="form.background" rows="3" placeholder="补充行业、公司、时间范围等背景" />
        </label>
        <label>
          <span>关注点</span>
          <textarea v-model="form.focus_points" rows="3" placeholder="真实性、来源质量、近期动态、风险信息等" />
        </label>
        <label class="inline">
          <input v-model="form.use_default_targets" type="checkbox" />
          <span>创建时加载默认评测目标</span>
        </label>
        <button class="button primary" type="submit" :disabled="submitting">创建并进入配置</button>
      </form>
    </SectionPanel>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import SectionPanel from '../components/SectionPanel.vue'
import { createTask } from '../api/platform'

const router = useRouter()
const submitting = ref(false)
const form = reactive({
  name: '',
  description: '',
  task_type: 'web_search',
  background: '',
  focus_points: '',
  use_default_targets: true
})

async function submit() {
  submitting.value = true
  try {
    const task = await createTask(form)
    router.push(`/tasks/${task.id}`)
  } finally {
    submitting.value = false
  }
}
</script>
