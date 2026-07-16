<template>
  <div class="page">
    <div class="page-title">
      <div>
        <h1>任务流水线</h1>
        <p>输入需求后生成任务、Prompt 和参数草稿，人工审核后再创建配置并运行测试。</p>
      </div>
      <RouterLink class="button" to="/tasks/new">普通创建</RouterLink>
    </div>

    <SectionPanel title="1. 输入需求" description="先写你的目标、约束和判断标准，越具体越好。">
      <div class="form">
        <textarea
          v-model="requirement"
          rows="6"
          placeholder="例如：我要做企业背调，重点核验招投标、行政处罚、股权风险、舆情风险，要求所有关键结论可追溯来源。"
        />
        <div class="actions">
          <button class="button primary" :disabled="!requirement.trim() || generating" @click="generateDraft">
            生成可审核草稿
          </button>
          <span v-if="generating" class="muted">正在调用 pipeline_planner...</span>
        </div>
      </div>
    </SectionPanel>

    <SectionPanel v-if="draft" title="2. 人工审核草稿" description="LLM 只生成建议，保存前请在这里直接修改。">
      <div class="helper">
        Agent：{{ draft.agent_name }} · 模型：{{ draft.agent_model }} · Prompt：{{ draft.prompt_location }}
      </div>

      <!-- 候选方案选择器 -->
      <div v-if="draft.candidates && draft.candidates.length > 1" class="candidate-selector">
        <h2>候选方案</h2>
        <div class="candidate-tabs">
          <button
            v-for="(cand, idx) in draft.candidates"
            :key="idx"
            :class="['candidate-tab', { active: selectedCandidateIndex === idx }]"
            @click="selectCandidate(idx)"
          >
            {{ cand.label }}
          </button>
        </div>
        <p v-if="selectedCandidate" class="candidate-rationale">{{ selectedCandidate.rationale }}</p>
      </div>

      <div class="workspace-grid">
        <div class="form compact">
          <h2>任务信息</h2>
          <label><span>任务名称</span><input v-model="draft.task.name" /></label>
          <label><span>任务描述</span><textarea v-model="draft.task.description" rows="3" /></label>
          <label><span>任务背景</span><textarea v-model="draft.task.background" rows="3" /></label>
          <label><span>关注点</span><textarea v-model="draft.task.focus_points" rows="3" /></label>
        </div>

        <div class="form compact">
          <h2>模型与参数</h2>
          <div class="field-grid">
            <label><span>Provider</span><input v-model="currentModel.provider" /></label>
            <label><span>模型</span><input v-model="currentModel.name" /></label>
            <label><span>temperature</span><input v-model.number="currentParameter.temperature" type="number" min="0" max="2" step="0.1" /></label>
            <label><span>top_p</span><input v-model.number="currentParameter.top_p" type="number" min="0" max="1" step="0.05" /></label>
            <label><span>max_tokens</span><input v-model.number="currentParameter.max_tokens" type="number" min="256" step="128" /></label>
            <label><span>搜索策略</span>
              <select v-model="currentParameter.search_strategy">
                <option value="turbo">turbo</option>
                <option value="max">max</option>
                <option value="agent">agent</option>
              </select>
            </label>
          </div>
          <label><span>参数组名称</span><input v-model="currentParameter.name" /></label>
          <label><span>模型推荐理由</span><textarea v-model="currentModel.rationale" rows="2" /></label>
          <label><span>参数推荐理由</span><textarea v-model="currentParameter.rationale" rows="3" /></label>
          <label class="inline"><input v-model="currentParameter.force_citations" type="checkbox" /> 强制来源引用</label>
          <label class="inline"><input v-model="currentParameter.enable_evaluator" type="checkbox" /> 启用评估 Agent</label>
          <label class="inline"><input v-model="currentParameter.enable_secondary_verification" type="checkbox" /> 评估 Agent 联网复核</label>
          <label class="inline"><input v-model="currentParameter.allow_model_memory" type="checkbox" /> 允许模型记忆补全事实</label>
        </div>
      </div>

      <div class="form compact">
        <h2>Prompt</h2>
        <div class="field-grid">
          <label><span>Prompt 名称</span><input v-model="currentPrompt.name" /></label>
          <label><span>版本</span><input v-model="currentPrompt.version" /></label>
        </div>
        <label><span>System Prompt</span><textarea v-model="currentPrompt.system_prompt" rows="14" /></label>
        <label><span>User Prompt</span><textarea v-model="currentPrompt.user_prompt" rows="4" /></label>
      </div>

      <div class="form compact">
        <h2>评测目标</h2>
        <div v-for="(target, index) in draft.evaluation_targets" :key="index" class="target-editor">
          <input v-model="target.name" />
          <input v-model.number="target.weight" type="number" min="0" max="100" />
          <textarea v-model="target.description" rows="2" />
        </div>
      </div>

      <div class="review-grid">
        <div>
          <h2>假设</h2>
          <ul class="issue-list">
            <li v-for="item in draft.assumptions" :key="item"><span>{{ item }}</span></li>
          </ul>
        </div>
        <div>
          <h2>人工审核重点</h2>
          <ul class="issue-list">
            <li v-for="item in draft.review_notes" :key="item"><span>{{ item }}</span></li>
          </ul>
        </div>
      </div>

      <div class="actions">
        <button class="button" :disabled="generating" @click="generateDraft">重新生成草稿</button>
        <button class="button" :disabled="committing" @click="commitOnly">确认创建配置</button>
        <button class="button primary" :disabled="committing || running" @click="commitAndRun">确认创建并运行测试</button>
      </div>
    </SectionPanel>

    <SectionPanel v-if="commitResult" title="3. 已创建配置">
      <div class="output-meta">
        <span>任务 #{{ commitResult.task.id }}</span>
        <span>Prompt #{{ commitResult.prompt.id }}</span>
        <span>{{ commitResult.model.name }}</span>
        <span>{{ commitResult.parameter.search_strategy }}</span>
      </div>
      <div class="actions">
        <RouterLink class="button" :to="`/tasks/${commitResult.task.id}`">进入任务详情</RouterLink>
        <button class="button primary" :disabled="running" @click="runCommittedTask">运行测试</button>
      </div>
    </SectionPanel>

    <SectionPanel v-if="running || runStatus" title="4. 流水线测试">
      <p>{{ runStatus }}</p>
    </SectionPanel>

    <SectionPanel v-if="markdownReport" title="标准 Markdown 报告">
      <pre class="report">{{ markdownReport }}</pre>
    </SectionPanel>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import SectionPanel from '../components/SectionPanel.vue'
import {
  commitPipelineDraft,
  createBatch,
  generatePipelineDraft,
  getBatch,
  getReport,
  runBatch
} from '../api/platform'
import type { Batch, PipelineCandidateDraft, PipelineCommitResult, PipelineDraft } from '../types'

const requirement = ref('')
const draft = ref<PipelineDraft | null>(null)
const commitResult = ref<PipelineCommitResult | null>(null)
const generating = ref(false)
const committing = ref(false)
const running = ref(false)
const runStatus = ref('')
const markdownReport = ref('')
const selectedCandidateIndex = ref(0)

const selectedCandidate = computed<PipelineCandidateDraft | null>(() => {
  if (!draft.value?.candidates?.length) return null
  const idx = selectedCandidateIndex.value
  return draft.value.candidates[idx] ?? draft.value.candidates[0] ?? null
})

const currentPrompt = computed(() => {
  if (selectedCandidate.value) return selectedCandidate.value.prompt
  return draft.value?.prompt ?? { name: '', version: 'v1', system_prompt: '', user_prompt: '' }
})

const currentModel = computed(() => {
  if (selectedCandidate.value) return selectedCandidate.value.model
  return draft.value?.model ?? { provider: '', name: '', base_url: '', api_key_ref: '', is_enabled: true, rationale: '' }
})

const currentParameter = computed(() => {
  if (selectedCandidate.value) return selectedCandidate.value.parameter
  return draft.value?.parameter ?? {
    name: '', temperature: 0.2, top_p: 0.9, max_tokens: 3000, search_limit: 5,
    search_strategy: 'turbo', force_citations: true, require_structured_output: true,
    enable_evaluator: true, enable_secondary_verification: false, allow_model_memory: false,
    is_enabled: true, rationale: ''
  }
})

function selectCandidate(idx: number) {
  selectedCandidateIndex.value = idx
  if (draft.value) {
    draft.value.selected_candidate_index = idx
  }
}

async function generateDraft() {
  generating.value = true
  try {
    draft.value = await generatePipelineDraft(requirement.value)
    selectedCandidateIndex.value = draft.value.selected_candidate_index ?? 0
    commitResult.value = null
    markdownReport.value = ''
    runStatus.value = ''
  } finally {
    generating.value = false
  }
}

async function commitOnly() {
  await ensureCommitted()
}

async function commitAndRun() {
  await ensureCommitted()
  await runCommittedTask()
}

async function ensureCommitted() {
  if (commitResult.value || !draft.value) return
  committing.value = true
  try {
    commitResult.value = await commitPipelineDraft(draft.value)
  } finally {
    committing.value = false
  }
}

async function runCommittedTask() {
  if (!commitResult.value) return
  running.value = true
  markdownReport.value = ''
  try {
    const taskId = commitResult.value.task.id
    const promptId = commitResult.value.prompt.id
    const created = await createBatch(taskId, `流水线测试 ${new Date().toLocaleString()}`, [promptId])
    await runBatch(created.batch.id)
    runStatus.value = '测试已启动，正在等待结果...'
    const completed = await waitForBatch(created.batch.id)
    runStatus.value = `测试${completed.status === 'completed' ? '完成' : '结束'}：${completed.status}`
    try {
      const report = await getReport(created.batch.id)
      markdownReport.value = report.content
    } catch {
      markdownReport.value = summarizeBatch(completed)
    }
  } finally {
    running.value = false
  }
}

async function waitForBatch(batchId: number) {
  for (let index = 0; index < 120; index += 1) {
    const batch = await getBatch(batchId)
    if (batch.status === 'completed' || batch.status === 'failed') return batch
    runStatus.value = `测试运行中：${progressText(batch)}`
    await sleep(2000)
  }
  return await getBatch(batchId)
}

function progressText(batch: Batch) {
  const progress = batch.progress || {}
  return `${progress.completed || 0}/${progress.total || 0} 完成，${progress.failed || 0} 失败`
}

function summarizeBatch(batch: Batch) {
  const lines = [`# 流水线测试结果`, '', `状态：${batch.status}`, `耗时：${batch.duration_ms} ms`, '']
  for (const combo of batch.combinations || []) {
    lines.push(`## 组合 #${combo.id}`)
    lines.push(`- Prompt：${combo.prompt_name}`)
    lines.push(`- 模型：${combo.model_name}`)
    lines.push(`- 参数：${combo.parameter_name}`)
    lines.push(`- 总分：${combo.evaluation?.total_score ?? '-'}`)
    lines.push(`- 风险：${combo.evaluation?.risk_level ?? '-'}`)
    lines.push('')
    lines.push(combo.result?.raw_output || combo.result?.error_message || '暂无输出')
    lines.push('')
  }
  return lines.join('\n')
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
</script>

<style scoped>
.candidate-selector {
  margin-bottom: 1.5rem;
}

.candidate-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.candidate-tab {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #f9f9f9;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.candidate-tab:hover {
  background: #e9e9e9;
}

.candidate-tab.active {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.candidate-rationale {
  padding: 0.75rem;
  background: #f0f7ff;
  border-left: 3px solid #007bff;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #555;
  margin: 0;
}
</style>
