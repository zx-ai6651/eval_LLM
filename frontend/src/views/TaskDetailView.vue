<template>
  <div class="page">
    <div class="page-title">
      <div>
        <h1>{{ task?.name || '任务详情' }}</h1>
        <p>{{ task?.description || '配置 Prompt、模型、参数并启动测试批次。' }}</p>
      </div>
      <div class="title-actions">
        <RouterLink class="button" to="/tasks">返回任务列表</RouterLink>
        <button class="button danger" @click="archiveCurrentTask">删除任务</button>
      </div>
    </div>

    <div class="workspace-grid">
      <SectionPanel title="Prompt 管理" description="添加一个或多个候选 Prompt。">
        <form class="form compact" @submit.prevent="savePrompt">
          <input v-model="promptForm.name" placeholder="Prompt 名称" required />
          <input v-model="promptForm.version" placeholder="版本，例如 v1" />
          <textarea
            v-model="promptForm.system_prompt"
            rows="8"
            placeholder="System Prompt：角色、搜索要求、来源引用、禁止编造、时间线要求等"
            required
          />
          <textarea v-model="promptForm.user_prompt" rows="4" placeholder="User Prompt，可选：每次任务附加的用户侧指令" />
          <button class="button primary" type="submit">添加 Prompt</button>
        </form>
        <ul class="item-list">
          <li
            v-for="prompt in prompts"
            :key="prompt.id"
            class="item-with-tooltip"
            :data-tooltip="shortDetail(promptDetail(prompt))"
            :title="shortDetail(promptDetail(prompt))"
            @click="showConfigDetail(`Prompt：${prompt.name}`, promptDetail(prompt))"
          >
            <div>
              <strong>{{ prompt.name }}</strong>
              <span>{{ prompt.version }} · {{ prompt.user_prompt ? '含 User Prompt' : '仅 System Prompt' }}</span>
            </div>
            <div class="actions">
              <button class="button small" @click.stop="showConfigDetail(`Prompt：${prompt.name}`, promptDetail(prompt))">查看</button>
              <button class="button small danger" @click.stop="removePrompt(prompt.id)">删除</button>
            </div>
          </li>
        </ul>
      </SectionPanel>

      <SectionPanel title="模型配置" description="第一阶段按 OpenAI-compatible 格式保存。">
        <form class="form compact" @submit.prevent="saveModel">
          <select v-model="modelForm.provider">
            <option v-for="provider in modelAdapters.providers" :key="provider.name" :value="provider.name">
              {{ provider.label }}
            </option>
          </select>
          <input v-model="modelForm.name" placeholder="模型名称，例如 deepseek-chat / qwen-plus" required />
          <input v-model="modelForm.base_url" placeholder="base_url，可留空走统一配置文件" />
          <input v-model="modelForm.api_key_ref" placeholder="API Key 或环境变量名，可留空走统一配置文件" type="password" />
          <button class="button primary" type="submit">添加模型</button>
        </form>
        <div class="helper">
          当前智能体模型配置来自 <code>config/model_adapters.json</code>
          <span v-for="(agent, key) in modelAdapters.agents" :key="key">
            {{ agent.label }}={{ agent.provider }}/{{ agent.model }}
          </span>
        </div>
        <ul class="item-list">
          <li
            v-for="model in models"
            :key="model.id"
            class="item-with-tooltip"
            :data-tooltip="modelDetail(model)"
            :title="modelDetail(model)"
            @click="showConfigDetail(`模型：${model.name}`, modelDetail(model))"
          >
            <div>
              <strong>{{ model.name }}</strong>
              <span>{{ model.provider }} · {{ model.is_enabled ? '启用' : '禁用' }}</span>
            </div>
            <div class="actions">
              <button class="button small" @click.stop="showConfigDetail(`模型：${model.name}`, modelDetail(model))">查看</button>
              <button class="button small danger" @click.stop="removeModel(model.id)">删除</button>
            </div>
          </li>
        </ul>
      </SectionPanel>
    </div>

    <div class="workspace-grid">
      <SectionPanel title="参数配置" description="配置多组基础参数参与组合测试。">
        <form class="form compact" @submit.prevent="saveParameter">
          <input v-model="parameterForm.name" placeholder="参数组名称" required />
          <div class="field-grid">
            <label>
              <span>temperature</span>
              <input v-model.number="parameterForm.temperature" type="number" min="0" max="2" step="0.1" />
            </label>
            <label>
              <span>top_p</span>
              <input v-model.number="parameterForm.top_p" type="number" min="0" max="1" step="0.05" />
            </label>
            <label>
              <span>max_tokens</span>
              <input v-model.number="parameterForm.max_tokens" type="number" min="256" step="128" />
            </label>
            <label>
              <span>搜索条数</span>
              <input v-model.number="parameterForm.search_limit" type="number" min="1" max="10" />
            </label>
            <label>
              <span>百炼搜索策略</span>
              <select v-model="parameterForm.search_strategy">
                <option value="default">默认配置（turbo）</option>
                <option value="turbo">低成本 turbo</option>
                <option value="max">高质量 max</option>
                <option value="agent">Agent 策略（高成本）</option>
              </select>
            </label>
          </div>
          <div class="helper">
            Agent 策略会显著增加 token 消耗；被测参数使用 agent 时，评估 Agent 会自动联网复核。
          </div>
          <label class="inline"><input v-model="parameterForm.force_citations" type="checkbox" /> 强制来源引用</label>
          <label class="inline"><input v-model="parameterForm.require_structured_output" type="checkbox" /> 要求结构化输出</label>
          <label class="inline"><input v-model="parameterForm.enable_evaluator" type="checkbox" /> 启用评估 Agent</label>
          <label class="inline">
            <input v-model="parameterForm.enable_secondary_verification" type="checkbox" /> 评估 Agent 联网复核
          </label>
          <label class="inline"><input v-model="parameterForm.allow_model_memory" type="checkbox" /> 允许模型记忆补全事实</label>
          <button class="button primary" type="submit">添加参数组</button>
        </form>
        <ul class="item-list">
          <li
            v-for="parameter in parameters"
            :key="parameter.id"
            class="item-with-tooltip"
            :data-tooltip="parameterDetail(parameter)"
            :title="parameterDetail(parameter)"
            @click="showConfigDetail(`参数：${parameter.name}`, parameterDetail(parameter))"
          >
            <div>
              <strong>{{ parameter.name }}</strong>
              <span>
                temp {{ parameter.temperature }} · top_p {{ parameter.top_p }} · 搜索 {{ parameter.search_limit }} · 策略
                {{ parameter.search_strategy || 'default' }} · 复核 {{ parameter.enable_secondary_verification ? '开' : '关' }}
              </span>
            </div>
            <div class="actions">
              <button class="button small" @click.stop="showConfigDetail(`参数：${parameter.name}`, parameterDetail(parameter))">查看</button>
              <button class="button small danger" @click.stop="removeParameter(parameter.id)">删除</button>
            </div>
          </li>
        </ul>
      </SectionPanel>

      <SectionPanel title="评测目标与权重" description="默认真实性优先，可按任务调整。">
        <div class="target-list">
          <label v-for="target in targets" :key="target.id" class="target-row">
            <span>{{ target.name }}</span>
            <input
              :value="target.weight"
              type="number"
              min="0"
              max="100"
              @change="updateWeightFromEvent(target.id, $event)"
            />
          </label>
        </div>
      </SectionPanel>
    </div>

    <SectionPanel v-if="selectedConfigDetail" :title="selectedConfigDetail.title" description="已保存配置详情">
      <template #actions>
        <button class="button small" @click="selectedConfigDetail = null">关闭</button>
      </template>
      <pre class="report">{{ selectedConfigDetail.content }}</pre>
    </SectionPanel>

    <SectionPanel title="Prompt 诊断与优化" description="基于已有测试结果诊断当前 Prompt，并生成一个可复测的优化版。">
      <div class="optimization-grid">
        <div class="form compact">
          <label>
            <span>选择 Prompt</span>
            <select v-model.number="optimizationForm.prompt_id">
              <option :value="0">请选择 Prompt</option>
              <option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
                {{ prompt.name }} · {{ prompt.version }}
              </option>
            </select>
          </label>
          <label>
            <span>参考批次</span>
            <select v-model.number="optimizationForm.batch_id" @change="loadOptimizationBatch">
              <option :value="0">自动选择最近结果</option>
              <option v-for="batch in batches" :key="batch.id" :value="batch.id">
                {{ batch.name }} · {{ batch.status }}
              </option>
            </select>
          </label>
          <label>
            <span>参考组合</span>
            <select v-model.number="optimizationForm.combination_id">
              <option :value="0">自动选择该 Prompt 的最近组合</option>
              <option v-for="combo in optimizationBatch?.combinations || []" :key="combo.id" :value="combo.id">
                #{{ combo.id }} · {{ combo.prompt_name }} · {{ combo.evaluation?.total_score ?? '未评分' }}
              </option>
            </select>
          </label>
          <div class="actions">
            <button class="button" type="button" :disabled="!optimizationForm.prompt_id || optimizingAction" @click="diagnoseSelectedPrompt">
              {{ optimizingAction ? '处理中...' : '诊断 Prompt' }}
            </button>
            <button class="button primary" type="button" :disabled="!optimizationForm.prompt_id || optimizingAction" @click="optimizeSelectedPrompt">
              优化 Prompt
            </button>
          </div>
          <p v-if="optimizationStatus" class="helper">{{ optimizationStatus }}</p>
          <p v-if="optimizationError" class="helper error-text">{{ optimizationError }}</p>
        </div>

        <div v-if="diagnosis" class="diagnosis-block">
          <h3>诊断结果</h3>
          <p class="helper">
            Agent：{{ diagnosis.agent_name }} · 模型：{{ diagnosis.agent_model }} · Prompt：{{ diagnosis.prompt_location }}
          </p>
          <p>{{ diagnosis.summary }}</p>
          <ul class="issue-list">
            <li v-for="issue in diagnosis.issues" :key="`${issue.type}-${issue.severity}`">
              <strong>{{ issue.type }} · {{ issue.severity }}</strong>
              <span>{{ issue.evidence }}</span>
              <span>{{ issue.suggestion }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="optimizationResult" class="optimization-result">
        <div class="prompt-compare">
          <label>
            <span>原 Prompt</span>
            <textarea :value="selectedOptimizationPrompt?.system_prompt || selectedOptimizationPrompt?.content || ''" rows="12" readonly />
          </label>
          <label>
            <span>优化版 Prompt</span>
            <textarea v-model="optimizedDraft.system_prompt" rows="12" />
          </label>
        </div>
        <label>
          <span>优化版 User Prompt</span>
          <textarea v-model="optimizedDraft.user_prompt" rows="4" />
        </label>
        <div class="report optimization-note">
          <strong>优化说明</strong>
          <p>
            Agent：{{ optimizationResult.agent_name }} · 模型：{{ optimizationResult.agent_model }} · Prompt：{{
              optimizationResult.prompt_location
            }}
          </p>
          <p>{{ optimizationResult.change_summary }}</p>
          <p>{{ optimizationResult.recommendation }}</p>
        </div>
        <div class="run-bar">
          <input v-model="optimizationForm.save_name" placeholder="优化版 Prompt 名称" />
          <button class="button primary" type="button" :disabled="optimizingAction" @click="saveOptimizationAsPrompt">
            保存为新 Prompt
          </button>
        </div>
      </div>

      <div v-if="savedOptimizedPrompt" class="helper">
        已保存：<strong>{{ savedOptimizedPrompt.name }}</strong>。可在上方 Prompt 列表中启用它，并复用现有批次测试流程。
      </div>

      <div v-if="compareResult" class="comparison-strip">
        <span>原分数：{{ compareResult.original_score ?? '-' }}</span>
        <span>优化分数：{{ compareResult.optimized_score ?? '-' }}</span>
        <span>总分变化：{{ compareResult.total_delta ?? '-' }}</span>
        <span>真实性变化：{{ compareResult.truthfulness_delta ?? '-' }}</span>
        <span>{{ compareResult.recommendation }}</span>
      </div>
    </SectionPanel>

    <SectionPanel title="测试运行" description="生成配置组合并启动批次，页面会轮询更新运行状态。">
      <template #actions>
        <button class="button" @click="refreshAll">刷新</button>
      </template>
      <div class="run-bar">
        <input v-model="batchName" placeholder="批次名称" />
        <button class="button primary" @click="createAndRun" :disabled="runningAction">生成并启动测试</button>
      </div>
      <div class="test-scope-panel">
        <div class="scope-options">
          <label class="scope-option" :class="{ active: runPromptScope === 'selected' }">
            <input v-model="runPromptScope" type="radio" value="selected" />
            <span>只测试选中 Prompt</span>
          </label>
          <label class="scope-option" :class="{ active: runPromptScope === 'all' }">
            <input v-model="runPromptScope" type="radio" value="all" />
            <span>测试全部启用 Prompt</span>
          </label>
        </div>
        <select v-model.number="selectedRunPromptId" :disabled="runPromptScope !== 'selected'">
          <option :value="0">请选择本批次要测试的 Prompt</option>
          <option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
            {{ prompt.name }} · {{ prompt.version }} · {{ prompt.source_type || 'manual' }}
          </option>
        </select>
        <p class="helper">
          当前范围：{{ runScopeSummary }}
        </p>
      </div>
      <table>
        <thead>
          <tr>
            <th>批次</th>
            <th>状态</th>
            <th>进度</th>
            <th>耗时</th>
            <th>成本</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="batch in batches" :key="batch.id">
            <td>{{ batch.name }}</td>
            <td><StatusBadge :status="batch.status" /></td>
            <td>{{ progressText(rowBatch(batch)) }}</td>
            <td>{{ formatDuration(rowBatch(batch)) }}</td>
            <td>{{ formatMoney(rowBatch(batch).total_cost) }}</td>
            <td class="actions">
              <button class="button small" @click="selectBatch(batch.id)">查看</button>
              <button class="button small danger" @click="removeBatch(batch.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </SectionPanel>

    <SectionPanel v-if="selectedBatch" title="结果对比" description="按组合查看输出、评分、风险和问题摘要。">
      <table>
        <thead>
          <tr>
            <th>组合</th>
            <th>Prompt</th>
            <th>模型</th>
            <th>参数</th>
            <th>状态</th>
            <th>总分</th>
            <th>真实性</th>
            <th>风险</th>
            <th>问题摘要</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="combo in sortedCombinations" :key="combo.id">
            <tr>
              <td>#{{ combo.id }}</td>
              <td>{{ combo.prompt_name }}</td>
              <td>{{ combo.model_name }}</td>
              <td>{{ combo.parameter_name }}</td>
              <td><StatusBadge :status="combo.status" /></td>
              <td>{{ combo.evaluation?.total_score ?? '-' }}</td>
              <td>{{ combo.evaluation?.truthfulness_score ?? '-' }}</td>
              <td>{{ combo.evaluation?.risk_level ?? '-' }}</td>
              <td>
                <button
                  class="button small issue-toggle"
                  :class="{ danger: hasIssueText(combo) }"
                  :disabled="!hasIssueText(combo)"
                  @click="toggleIssueSummary(combo.id)"
                >
                  {{ hasIssueText(combo) ? `查看问题 ${issueCount(combo)}` : '无问题' }}
                </button>
              </td>
              <td><button class="button small" @click="selectedCombination = combo">查看输出</button></td>
            </tr>
            <tr v-if="expandedIssueComboId === combo.id" class="issue-detail-row">
              <td colspan="10">
                <pre class="issue-detail">{{ issueText(combo) }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </SectionPanel>

    <SectionPanel v-if="selectedCombination" title="LLM 原始输出" description="当前组合的模型原始生成内容、来源与执行日志。">
      <template #actions>
        <button class="button small" @click="selectedCombination = null">关闭</button>
      </template>
      <div class="output-meta">
        <span>组合 #{{ selectedCombination.id }}</span>
        <span>{{ selectedCombination.prompt_name }}</span>
        <span>{{ selectedCombination.model_name }}</span>
        <span>{{ selectedCombination.parameter_name }}</span>
      </div>
      <pre class="report">{{ selectedCombination.result?.raw_output || selectedCombination.result?.error_message || '暂无输出' }}</pre>
      <details class="details-block">
        <summary>来源与执行日志</summary>
        <pre class="report">{{ prettyResultMeta(selectedCombination) }}</pre>
      </details>
      <details class="details-block" v-if="selectedCombination.evaluation?.rule_metrics_json">
        <summary>评分规则指标</summary>
        <pre class="report">{{ prettyRuleMetrics(selectedCombination) }}</pre>
      </details>
    </SectionPanel>

    <SectionPanel v-if="report" title="测试报告">
      <pre class="report">{{ report.content }}</pre>
    </SectionPanel>

    <SectionPanel title="优化方案 Agent" description="基于已完成批次的测试结果，生成全方位配置优化方案（Prompt、参数、模型）。">
      <div class="optimization-plan-controls">
        <label>
          <span>选择已完成批次</span>
          <select v-model.number="optimizationPlanBatchId">
            <option :value="0">请选择批次</option>
            <option v-for="batch in completedBatches" :key="batch.id" :value="batch.id">
              {{ batch.name }} · 总分 {{ batchAvgScore(batch) }}
            </option>
          </select>
        </label>
        <button
          class="button primary"
          :disabled="!optimizationPlanBatchId || optimizationPlanLoading"
          @click="generateOptimizationPlan"
        >
          {{ optimizationPlanLoading ? '生成中...' : '生成优化方案' }}
        </button>
        <button class="button" @click="loadOptimizationPlans">刷新列表</button>
      </div>
      <p v-if="optimizationPlanError" class="helper error-text">{{ optimizationPlanError }}</p>
      <p v-if="optimizationPlanStatus" class="helper">{{ optimizationPlanStatus }}</p>

      <div class="optimize-retest-controls">
        <h3>一键优化并复测</h3>
        <p class="helper">自动执行：生成方案 → 应用配置 → 创建新批次 → 运行测试 → 对比评分，最多迭代指定轮数。</p>
        <label>
          <span>最大迭代轮数</span>
          <input v-model.number="optimizeRetestMaxRounds" type="number" min="1" max="10" />
        </label>
        <button
          class="button primary"
          :disabled="!optimizationPlanBatchId || optimizeRetestLoading || optimizationPlanLoading"
          @click="runOptimizeAndRetest"
        >
          {{ optimizeRetestLoading ? '优化复测中...' : '一键优化并复测' }}
        </button>
      </div>
      <p v-if="optimizeRetestError" class="helper error-text">{{ optimizeRetestError }}</p>
      <p v-if="optimizeRetestStatus" class="helper">{{ optimizeRetestStatus }}</p>

      <div v-if="optimizationPlans.length" class="optimization-plan-list">
        <h3>历史优化方案</h3>
        <ul class="item-list">
          <li
            v-for="plan in optimizationPlans"
            :key="plan.id"
            :class="{ active: selectedOptimizationPlan?.id === plan.id }"
            @click="selectedOptimizationPlan = plan"
          >
            <div>
              <strong>第 {{ plan.round_number }} 轮</strong>
              <span>
                {{ plan.status }} · {{ plan.agent_name }} · {{ plan.actions.length }} 个动作
                <span v-if="plan.stop_optimization" class="badge-stop">建议停止</span>
              </span>
            </div>
            <div class="actions">
              <button class="button small" @click.stop="selectedOptimizationPlan = plan">查看</button>
              <button
                v-if="plan.status === 'draft'"
                class="button small primary"
                :disabled="optimizationPlanLoading"
                @click.stop="applySelectedPlan(plan)"
              >
                应用
              </button>
            </div>
          </li>
        </ul>
      </div>

      <div v-if="selectedOptimizationPlan" class="optimization-plan-detail">
        <h3>方案详情 — 第 {{ selectedOptimizationPlan.round_number }} 轮</h3>
        <div class="plan-meta">
          <span>状态：{{ selectedOptimizationPlan.status }}</span>
          <span>Agent：{{ selectedOptimizationPlan.agent_name }} / {{ selectedOptimizationPlan.agent_model }}</span>
          <span>来源批次：#{{ selectedOptimizationPlan.source_batch_id }}</span>
        </div>
        <div class="plan-summary">
          <strong>总结</strong>
          <p>{{ selectedOptimizationPlan.summary }}</p>
        </div>
        <div v-if="selectedOptimizationPlan.diagnosis && Object.keys(selectedOptimizationPlan.diagnosis).length" class="plan-diagnosis">
          <strong>诊断数据</strong>
          <div class="diagnosis-stats">
            <span v-if="selectedOptimizationPlan.diagnosis.avg_total_score">
              平均总分：{{ selectedOptimizationPlan.diagnosis.avg_total_score }}
            </span>
            <span v-if="selectedOptimizationPlan.diagnosis.avg_truthfulness_score">
              平均真实性：{{ selectedOptimizationPlan.diagnosis.avg_truthfulness_score }}
            </span>
            <span v-if="selectedOptimizationPlan.diagnosis.completed_combinations">
              完成组合数：{{ selectedOptimizationPlan.diagnosis.completed_combinations }}
            </span>
          </div>
        </div>
        <div class="plan-actions">
          <strong>优化动作（{{ selectedOptimizationPlan.actions.length }}）</strong>
          <table>
            <thead>
              <tr>
                <th>类型</th>
                <th>目标 ID</th>
                <th>理由</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(action, idx) in selectedOptimizationPlan.actions" :key="idx">
                <td><span class="action-type-badge">{{ actionTypeLabel(action.type) }}</span></td>
                <td>{{ action.target_id ?? '新建' }}</td>
                <td>{{ action.rationale }}</td>
                <td><pre class="action-details">{{ JSON.stringify(action.details, null, 2) }}</pre></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="plan-recommendation">
          <strong>建议</strong>
          <p>{{ selectedOptimizationPlan.recommendation }}</p>
        </div>
        <div v-if="selectedOptimizationPlan.new_prompt_ids.length || selectedOptimizationPlan.new_model_ids.length || selectedOptimizationPlan.new_parameter_ids.length" class="plan-created-ids">
          <strong>已创建的配置</strong>
          <span v-if="selectedOptimizationPlan.new_prompt_ids.length">Prompt IDs: {{ selectedOptimizationPlan.new_prompt_ids.join(', ') }}</span>
          <span v-if="selectedOptimizationPlan.new_model_ids.length">模型 IDs: {{ selectedOptimizationPlan.new_model_ids.join(', ') }}</span>
          <span v-if="selectedOptimizationPlan.new_parameter_ids.length">参数 IDs: {{ selectedOptimizationPlan.new_parameter_ids.join(', ') }}</span>
        </div>
      </div>
    </SectionPanel>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import SectionPanel from '../components/SectionPanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import {
  addModel,
  addParameter,
  addPrompt,
  applyOptimizationPlan,
  comparePrompts,
  createBatch,
  createOptimizationPlan,
  deleteBatch,
  deleteModel,
  deleteParameter,
  deletePrompt,
  deleteTask,
  diagnosePrompt,
  getBatch,
  getReport,
  getTask,
  listBatches,
  listModelAdapters,
  listModels,
  listOptimizationPlans,
  listParameters,
  listPrompts,
  listTargets,
  optimizeAndRetest,
  optimizePrompt,
  runBatch,
  saveOptimizedPrompt,
  updateTarget
} from '../api/platform'
import type {
  Batch,
  Combination,
  EvaluationTarget,
  ModelConfig,
  OptimizationPlan,
  ParameterConfig,
  Prompt,
  PromptCompareResult,
  PromptDiagnosis,
  PromptOptimizationResult,
  Report,
  Task
} from '../types'
import { formatMoney } from '../utils/format'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<Task | null>(null)
const prompts = ref<Prompt[]>([])
const models = ref<ModelConfig[]>([])
const parameters = ref<ParameterConfig[]>([])
const targets = ref<EvaluationTarget[]>([])
const batches = ref<Batch[]>([])
const selectedBatch = ref<Batch | null>(null)
const selectedCombination = ref<Combination | null>(null)
const expandedIssueComboId = ref<number | null>(null)
const selectedConfigDetail = ref<{ title: string; content: string } | null>(null)
const report = ref<Report | null>(null)
const modelAdapters = ref<any>({ providers: [], agents: {} })
const runningAction = ref(false)
const optimizingAction = ref(false)
const batchName = ref(`测试批次 ${new Date().toLocaleString()}`)
const runPromptScope = ref<'selected' | 'all'>('selected')
const selectedRunPromptId = ref(0)
let timer: number | undefined

const promptForm = reactive({
  name: '基础联网搜索 Prompt',
  version: 'v1',
  system_prompt: defaultSystemPrompt(),
  user_prompt: ''
})
const modelForm = reactive({ name: 'qwen-plus', provider: 'bailian', base_url: '', api_key_ref: '', is_enabled: true })
const parameterForm = reactive({
  name: '保守核验参数',
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 1800,
  search_limit: 5,
  search_strategy: 'turbo',
  force_citations: true,
  require_structured_output: true,
  enable_evaluator: true,
  allow_model_memory: false,
  enable_secondary_verification: false,
  is_enabled: true
})
const optimizationForm = reactive({
  prompt_id: 0,
  batch_id: 0,
  combination_id: 0,
  save_name: '优化版 Prompt'
})
const optimizationBatch = ref<Batch | null>(null)
const diagnosis = ref<PromptDiagnosis | null>(null)
const optimizationResult = ref<PromptOptimizationResult | null>(null)
const savedOptimizedPrompt = ref<Prompt | null>(null)
const compareResult = ref<PromptCompareResult | null>(null)
const optimizationStatus = ref('')
const optimizationError = ref('')
const optimizedDraft = reactive({
  system_prompt: '',
  user_prompt: ''
})

// ── 优化方案 Agent 状态 ──
const optimizationPlans = ref<OptimizationPlan[]>([])
const selectedOptimizationPlan = ref<OptimizationPlan | null>(null)
const optimizationPlanBatchId = ref(0)
const optimizationPlanLoading = ref(false)
const optimizationPlanError = ref('')
const optimizationPlanStatus = ref('')

// ── 一键优化复测状态 ──
const optimizeRetestLoading = ref(false)
const optimizeRetestMaxRounds = ref(3)
const optimizeRetestStatus = ref('')
const optimizeRetestError = ref('')

const sortedCombinations = computed(() => {
  const combos = selectedBatch.value?.combinations || []
  return [...combos].sort((a, b) => (b.evaluation?.total_score || 0) - (a.evaluation?.total_score || 0))
})
const selectedOptimizationPrompt = computed(() => prompts.value.find((prompt) => prompt.id === optimizationForm.prompt_id) || null)
const selectedRunPrompt = computed(() => prompts.value.find((prompt) => prompt.id === selectedRunPromptId.value) || null)
const runScopeSummary = computed(() => {
  if (runPromptScope.value === 'all') return `将测试全部 ${prompts.value.length} 个启用 Prompt。`
  return selectedRunPrompt.value ? `只测试：${selectedRunPrompt.value.name}` : '尚未选择 Prompt。'
})

onMounted(async () => {
  await refreshAll()
  await loadOptimizationPlans()
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

async function refreshAll() {
  task.value = await getTask(taskId)
  modelAdapters.value = await listModelAdapters()
  prompts.value = await listPrompts(taskId)
  models.value = await listModels(taskId)
  parameters.value = await listParameters(taskId)
  targets.value = await listTargets(taskId)
  batches.value = await listBatches(taskId)
  mergeSelectedBatchIntoList()
  ensureRunPromptSelection()
  if (selectedBatch.value) await selectBatch(selectedBatch.value.id)
  if (!optimizationForm.prompt_id && prompts.value.length) {
    optimizationForm.prompt_id = prompts.value[0].id
    optimizationForm.save_name = `${prompts.value[0].name} 优化版`
  }
}

async function savePrompt() {
  const draft = { ...promptForm }
  await addPrompt(taskId, { ...draft, content: draft.system_prompt })
  prompts.value = await listPrompts(taskId)
  Object.assign(promptForm, draft)
}

async function removePrompt(promptId: number) {
  if (!window.confirm('确定删除这个 Prompt 吗？历史测试引用会保留。')) return
  await deletePrompt(promptId)
  prompts.value = await listPrompts(taskId)
}

async function saveModel() {
  const draft = { ...modelForm }
  await addModel(taskId, draft)
  models.value = await listModels(taskId)
  Object.assign(modelForm, draft)
}

async function removeModel(modelId: number) {
  if (!window.confirm('确定删除这个模型配置吗？历史测试引用会保留。')) return
  await deleteModel(modelId)
  models.value = await listModels(taskId)
}

async function saveParameter() {
  const draft = { ...parameterForm }
  await addParameter(taskId, draft)
  parameters.value = await listParameters(taskId)
  Object.assign(parameterForm, draft)
}

async function removeParameter(parameterId: number) {
  if (!window.confirm('确定删除这组参数吗？历史测试引用会保留。')) return
  await deleteParameter(parameterId)
  parameters.value = await listParameters(taskId)
}

async function archiveCurrentTask() {
  if (!window.confirm('删除后任务会被归档，历史数据不会被物理移除。确定删除吗？')) return
  await deleteTask(taskId)
  window.location.href = '/tasks'
}

async function updateWeight(targetId: number, value: string) {
  await updateTarget(targetId, { weight: Number(value) })
  targets.value = await listTargets(taskId)
}

async function updateWeightFromEvent(targetId: number, event: Event) {
  const input = event.target as HTMLInputElement
  await updateWeight(targetId, input.value)
}

async function createAndRun() {
  runningAction.value = true
  try {
    ensureRunPromptSelection()
    if (runPromptScope.value === 'selected' && !selectedRunPromptId.value) {
      window.alert('请先选择本批次要测试的 Prompt。')
      return
    }
    const promptIds = runPromptScope.value === 'selected' ? [selectedRunPromptId.value] : undefined
    const created = await createBatch(taskId, batchName.value, promptIds)
    await runBatch(created.batch.id)
    await refreshAll()
    await selectBatch(created.batch.id)
    startPolling(created.batch.id)
  } finally {
    runningAction.value = false
  }
}

function ensureRunPromptSelection() {
  if (!prompts.value.length) {
    selectedRunPromptId.value = 0
    return
  }
  if (selectedRunPromptId.value && prompts.value.some((prompt) => prompt.id === selectedRunPromptId.value)) {
    return
  }
  if (savedOptimizedPrompt.value && prompts.value.some((prompt) => prompt.id === savedOptimizedPrompt.value?.id)) {
    selectedRunPromptId.value = savedOptimizedPrompt.value.id
    return
  }
  const latestOptimized = prompts.value.find((prompt) => prompt.source_type === 'optimized')
  selectedRunPromptId.value = latestOptimized?.id || prompts.value[0].id
}

async function removeBatch(batchId: number) {
  const batch = batches.value.find((item) => item.id === batchId)
  if (batch?.status === 'running' || batch?.status === 'queued') {
    window.alert('运行中或排队中的批次不能删除。')
    return
  }
  if (!window.confirm('确定删除这个测试批次吗？对应的组合结果、评分和报告会一起删除。')) return
  await deleteBatch(batchId)
  batches.value = await listBatches(taskId)
  if (selectedBatch.value?.id === batchId) {
    selectedBatch.value = null
    selectedCombination.value = null
    report.value = null
  }
  if (optimizationForm.batch_id === batchId) {
    optimizationForm.batch_id = 0
    optimizationForm.combination_id = 0
    optimizationBatch.value = null
    compareResult.value = null
  }
}

async function loadOptimizationBatch() {
  optimizationForm.combination_id = 0
  optimizationBatch.value = optimizationForm.batch_id ? await getBatch(optimizationForm.batch_id) : null
}

async function diagnoseSelectedPrompt() {
  if (!optimizationForm.prompt_id) return
  optimizingAction.value = true
  optimizationStatus.value = '正在调用 Prompt 诊断 Agent...'
  optimizationError.value = ''
  try {
    diagnosis.value = await diagnosePrompt(optimizationForm.prompt_id, {
      batch_id: optimizationForm.batch_id || null,
      combination_id: optimizationForm.combination_id || null
    })
    optimizationStatus.value = diagnosis.value.agent_name === 'rule_fallback' ? '已返回规则兜底诊断结果。' : '诊断完成。'
  } catch (error) {
    optimizationError.value = `诊断失败：${requestErrorMessage(error)}`
    optimizationStatus.value = ''
  } finally {
    optimizingAction.value = false
  }
}

async function optimizeSelectedPrompt() {
  if (!optimizationForm.prompt_id) return
  optimizingAction.value = true
  optimizationStatus.value = '正在准备 Prompt 优化...'
  optimizationError.value = ''
  try {
    if (!diagnosis.value) {
      optimizationStatus.value = '正在先执行 Prompt 诊断...'
      diagnosis.value = await diagnosePrompt(optimizationForm.prompt_id, {
        batch_id: optimizationForm.batch_id || null,
        combination_id: optimizationForm.combination_id || null
      })
    }
    optimizationStatus.value = '正在调用 Prompt 优化 Agent...'
    optimizationResult.value = await optimizePrompt(optimizationForm.prompt_id, {
      diagnosis: diagnosis.value,
      batch_id: optimizationForm.batch_id || null,
      combination_id: optimizationForm.combination_id || null
    })
    optimizedDraft.system_prompt = optimizationResult.value.optimized_system_prompt
    optimizedDraft.user_prompt = optimizationResult.value.optimized_user_prompt
    const prompt = selectedOptimizationPrompt.value
    optimizationForm.save_name = `${prompt?.name || 'Prompt'} 优化版`
    optimizationStatus.value = optimizationResult.value.agent_name === 'rule_fallback' ? '已返回规则兜底优化稿。' : '优化完成。'
  } catch (error) {
    optimizationError.value = `优化失败：${requestErrorMessage(error)}`
    optimizationStatus.value = ''
  } finally {
    optimizingAction.value = false
  }
}

function requestErrorMessage(error: unknown) {
  if (typeof error === 'object' && error) {
    const maybe = error as { response?: { data?: { detail?: string } }; message?: string }
    return maybe.response?.data?.detail || maybe.message || '未知错误'
  }
  return String(error || '未知错误')
}

async function saveOptimizationAsPrompt() {
  if (!optimizationForm.prompt_id || !optimizationResult.value) return
  optimizingAction.value = true
  try {
    savedOptimizedPrompt.value = await saveOptimizedPrompt(optimizationForm.prompt_id, {
      name: optimizationForm.save_name || '优化版 Prompt',
      system_prompt: optimizedDraft.system_prompt,
      user_prompt: optimizedDraft.user_prompt,
      optimization_note: optimizationResult.value.change_summary,
      version: 'optimized'
    })
    prompts.value = await listPrompts(taskId)
    runPromptScope.value = 'selected'
    selectedRunPromptId.value = savedOptimizedPrompt.value.id
    batchName.value = `${savedOptimizedPrompt.value.name} 测试批次 ${new Date().toLocaleString()}`
    compareResult.value = await comparePrompts({
      original_prompt_id: optimizationForm.prompt_id,
      optimized_prompt_id: savedOptimizedPrompt.value.id,
      original_batch_id: optimizationForm.batch_id || null
    })
  } finally {
    optimizingAction.value = false
  }
}

async function selectBatch(batchId: number) {
  selectedBatch.value = await getBatch(batchId)
  mergeSelectedBatchIntoList()
  selectedCombination.value = null
  expandedIssueComboId.value = null
  if (selectedBatch.value.status === 'completed') {
    try {
      report.value = await getReport(batchId)
    } catch {
      report.value = null
    }
  }
}

function startPolling(batchId: number) {
  if (timer) window.clearInterval(timer)
  timer = window.setInterval(async () => {
    await selectBatch(batchId)
    batches.value = await listBatches(taskId)
    mergeSelectedBatchIntoList()
    if (selectedBatch.value?.status === 'completed' || selectedBatch.value?.status === 'failed') {
      if (timer) window.clearInterval(timer)
      try {
        report.value = await getReport(batchId)
      } catch {
        report.value = null
      }
    }
  }, 2000)
}

function progressText(batch: Batch) {
  const progress = batch.progress || {}
  if (!progress.total) return batch.status === 'running' || batch.status === 'queued' ? '运行中' : '-'
  return `${progress.completed || 0}/${progress.total || 0} 完成，${progress.failed || 0} 失败`
}

function rowBatch(batch: Batch) {
  return selectedBatch.value?.id === batch.id ? { ...batch, ...selectedBatch.value } : batch
}

function mergeSelectedBatchIntoList() {
  if (!selectedBatch.value) return
  batches.value = batches.value.map((batch) => (batch.id === selectedBatch.value?.id ? { ...batch, ...selectedBatch.value } : batch))
}

function formatDuration(batch: Batch) {
  let ms = batch.duration_ms || 0
  if ((batch.status === 'running' || batch.status === 'queued') && batch.started_at) {
    ms = Math.max(ms, Date.now() - parseApiDateMs(batch.started_at))
  }
  if (ms >= 60000) return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
  if (ms >= 1000) return `${Math.floor(ms / 1000)}s`
  return `${Math.max(0, Math.round(ms))} ms`
}

function parseApiDateMs(value: string) {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasTimezone ? value : `${value}Z`).getTime()
}

function prettyResultMeta(combo: Combination) {
  const sources = safeJson(combo.result?.sources_json)
  const logs = safeJson(combo.result?.search_logs_json)
  return JSON.stringify({ sources, logs }, null, 2)
}

function prettyRuleMetrics(combo: Combination) {
  return JSON.stringify(safeJson(combo.evaluation?.rule_metrics_json), null, 2)
}

function issueText(combo: Combination) {
  return combo.evaluation?.issue_summary || combo.result?.error_message || ''
}

function hasIssueText(combo: Combination) {
  return Boolean(issueText(combo).trim())
}

function issueCount(combo: Combination) {
  const text = issueText(combo).trim()
  if (!text) return ''
  const bullets = text.split('\n').filter((line) => line.trim().startsWith('-')).length
  return bullets ? `(${bullets})` : ''
}

function toggleIssueSummary(comboId: number) {
  expandedIssueComboId.value = expandedIssueComboId.value === comboId ? null : comboId
}

function showConfigDetail(title: string, content: string) {
  selectedConfigDetail.value = { title, content }
}

function shortDetail(content: string) {
  const limit = 900
  return content.length > limit ? `${content.slice(0, limit)}\n...` : content
}

function promptDetail(prompt: Prompt) {
  return [
    `名称：${prompt.name}`,
    `版本：${prompt.version}`,
    `来源类型：${prompt.source_type || 'manual'}`,
    `父 Prompt：${prompt.parent_prompt_id || '-'}`,
    '',
    'System Prompt:',
    prompt.system_prompt || prompt.content || '-',
    '',
    'User Prompt:',
    prompt.user_prompt || '-',
    '',
    '优化说明:',
    prompt.optimization_note || '-'
  ].join('\n')
}

function modelDetail(model: ModelConfig) {
  return [
    `名称：${model.name}`,
    `Provider：${model.provider}`,
    `Base URL：${model.base_url || '使用统一配置'}`,
    `API Key：${model.api_key_ref ? '已配置 / 使用环境变量' : '使用统一配置或环境变量'}`,
    `状态：${model.is_enabled ? '启用' : '禁用'}`
  ].join('\n')
}

function parameterDetail(parameter: ParameterConfig) {
  return [
    `名称：${parameter.name}`,
    `temperature：${parameter.temperature}`,
    `top_p：${parameter.top_p}`,
    `max_tokens：${parameter.max_tokens}`,
    `search_limit：${parameter.search_limit}`,
    `search_strategy：${parameter.search_strategy || 'default'}`,
    `强制来源引用：${parameter.force_citations ? '是' : '否'}`,
    `要求结构化输出：${parameter.require_structured_output ? '是' : '否'}`,
    `启用评估 Agent：${parameter.enable_evaluator ? '是' : '否'}`,
    `评估 Agent 联网复核：${parameter.enable_secondary_verification ? '是' : '否'}`,
    `允许模型记忆补全：${parameter.allow_model_memory ? '是' : '否'}`,
    `状态：${parameter.is_enabled ? '启用' : '禁用'}`
  ].join('\n')
}

function safeJson(value?: string) {
  if (!value) return []
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function defaultSystemPrompt() {
  return [
    '你是一个联网搜索型信息核验 Agent。',
    '请只基于搜索结果回答，不要使用模型记忆补全事实。',
    '每个关键结论必须放入 claims；claim_type=fact 的结论必须绑定 source_ids。',
    '请区分 fact、inference 和 unknown。',
    '如果来源无法支撑结论，请放入 unverified_items，不要写成事实。',
    '输出必须是严格 JSON，不要 Markdown，不要代码块。',
    'JSON 字段必须包含 summary、claims、sources、risk_notes、unverified_items、search_queries_used。'
  ].join('\n')
}

// ── 优化方案 Agent 函数 ──

const completedBatches = computed(() => batches.value.filter((b) => b.status === 'completed'))

function batchAvgScore(batch: Batch): string {
  const combos = batch.combinations || []
  const scored = combos.filter((c) => c.evaluation)
  if (!scored.length) return '-'
  const avg = scored.reduce((sum, c) => sum + (c.evaluation?.total_score || 0), 0) / scored.length
  return avg.toFixed(1)
}

async function loadOptimizationPlans() {
  try {
    optimizationPlans.value = await listOptimizationPlans(taskId)
  } catch {
    optimizationPlans.value = []
  }
}

async function generateOptimizationPlan() {
  if (!optimizationPlanBatchId.value) return
  optimizationPlanLoading.value = true
  optimizationPlanError.value = ''
  optimizationPlanStatus.value = '正在调用优化方案 Agent，请稍候...'
  try {
    const plan = await createOptimizationPlan(optimizationPlanBatchId.value)
    optimizationPlanStatus.value = `优化方案已生成：${plan.actions.length} 个动作。`
    selectedOptimizationPlan.value = plan
    await loadOptimizationPlans()
  } catch (error) {
    optimizationPlanError.value = `生成失败：${requestErrorMessage(error)}`
    optimizationPlanStatus.value = ''
  } finally {
    optimizationPlanLoading.value = false
  }
}

async function applySelectedPlan(plan: OptimizationPlan) {
  if (!window.confirm(`确定应用第 ${plan.round_number} 轮优化方案吗？将创建新的 Prompt/参数/模型配置。`)) return
  optimizationPlanLoading.value = true
  optimizationPlanError.value = ''
  optimizationPlanStatus.value = '正在应用优化方案...'
  try {
    const updated = await applyOptimizationPlan(plan.id)
    optimizationPlanStatus.value = `优化方案已应用，创建了 ${updated.new_prompt_ids.length} 个 Prompt、${updated.new_model_ids.length} 个模型、${updated.new_parameter_ids.length} 个参数配置。`
    selectedOptimizationPlan.value = updated
    await loadOptimizationPlans()
    await refreshAll()
  } catch (error) {
    optimizationPlanError.value = `应用失败：${requestErrorMessage(error)}`
    optimizationPlanStatus.value = ''
  } finally {
    optimizationPlanLoading.value = false
  }
}

function actionTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    prompt_optimize: '优化 Prompt',
    prompt_new: '新建 Prompt',
    param_adjust: '调整参数',
    param_new: '新建参数',
    model_swap: '替换模型',
    verification_toggle: '切换核验',
    search_enhance: '搜索增强',
    structure_enforce: '结构强化'
  }
  return labels[type] || type
}

async function runOptimizeAndRetest() {
  if (!optimizationPlanBatchId.value) return
  if (!window.confirm(`确定对批次 #${optimizationPlanBatchId.value} 执行一键优化并复测吗？最多迭代 ${optimizeRetestMaxRounds.value} 轮，这将是一个长运行操作。`)) return
  optimizeRetestLoading.value = true
  optimizeRetestError.value = ''
  optimizeRetestStatus.value = '正在执行一键优化复测，请稍候（可能需要数分钟）...'
  try {
    const plan = await optimizeAndRetest(optimizationPlanBatchId.value, optimizeRetestMaxRounds.value)
    optimizeRetestStatus.value = `优化复测完成：第 ${plan.round_number} 轮，${plan.actions.length} 个动作。${plan.stop_optimization ? '（建议停止）' : ''}`
    selectedOptimizationPlan.value = plan
    await loadOptimizationPlans()
    await refreshAll()
  } catch (error) {
    optimizeRetestError.value = `一键优化复测失败：${requestErrorMessage(error)}`
    optimizeRetestStatus.value = ''
  } finally {
    optimizeRetestLoading.value = false
  }
}
</script>
