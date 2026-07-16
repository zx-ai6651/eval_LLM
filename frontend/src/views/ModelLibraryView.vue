<template>
  <div class="model-library">
    <div class="page-header">
      <h1>模型库管理</h1>
      <button @click="showAddDialog = true" class="btn btn-primary">
        + 添加模型
      </button>
    </div>

    <div class="filters">
      <label>
        <input type="checkbox" v-model="showActiveOnly" @change="loadModels" />
        仅显示启用的模型
      </label>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="models.length === 0" class="empty-state">
      <p>暂无模型数据</p>
      <p>点击"添加模型"按钮开始添加，或运行迁移脚本导入静态配置</p>
    </div>

    <div v-else class="model-table">
      <table>
        <thead>
          <tr>
            <th>提供商</th>
            <th>模型名称</th>
            <th>显示名称</th>
            <th>支持搜索</th>
            <th>特点标签</th>
            <th>平均评分</th>
            <th>测试次数</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="model in models" :key="model.id">
            <td>{{ model.provider }}</td>
            <td>{{ model.name }}</td>
            <td>{{ model.display_name || model.name }}</td>
            <td>
              <span :class="model.supports_search ? 'badge-success' : 'badge-secondary'">
                {{ model.supports_search ? '是' : '否' }}
              </span>
            </td>
            <td>
              <div class="characteristics">
                <span v-for="char in model.characteristics" :key="char" class="tag">
                  {{ char }}
                </span>
                <span v-if="!model.characteristics || model.characteristics.length === 0" class="text-muted">
                  无
                </span>
              </div>
            </td>
            <td>
              <span v-if="model.avg_total_score > 0" class="score">
                {{ model.avg_total_score.toFixed(1) }}
              </span>
              <span v-else class="text-muted">暂无</span>
            </td>
            <td>{{ model.total_test_count }}</td>
            <td>
              <span :class="model.is_active ? 'badge-success' : 'badge-warning'">
                {{ model.is_active ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="actions">
              <button @click="editModel(model)" class="btn btn-sm btn-secondary">编辑</button>
              <button 
                v-if="model.is_active"
                @click="deactivateModel(model.id)" 
                class="btn btn-sm btn-warning"
              >
                禁用
              </button>
              <button 
                v-else
                @click="activateModel(model.id)" 
                class="btn btn-sm btn-success"
              >
                启用
              </button>
              <button @click="refreshStats(model.id)" class="btn btn-sm btn-info">
                刷新统计
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 添加/编辑对话框 -->
    <div v-if="showAddDialog || editingModel" class="modal-overlay" @click.self="closeDialog">
      <div class="modal">
        <h2>{{ editingModel ? '编辑模型' : '添加模型' }}</h2>
        <form @submit.prevent="submitForm">
          <div class="form-group">
            <label>提供商 *</label>
            <input v-model="form.provider" required />
          </div>
          <div class="form-group">
            <label>模型名称 *</label>
            <input v-model="form.name" required />
          </div>
          <div class="form-group">
            <label>显示名称</label>
            <input v-model="form.display_name" />
          </div>
          <div class="form-group">
            <label>API Base URL</label>
            <input v-model="form.api_base" />
          </div>
          <div class="form-group">
            <label>API Key 环境变量</label>
            <input v-model="form.api_key_env" />
          </div>
          <div class="form-group">
            <label>
              <input type="checkbox" v-model="form.supports_search" />
              支持搜索
            </label>
          </div>
          <div class="form-group" v-if="form.supports_search">
            <label>搜索模式</label>
            <select v-model="form.search_mode">
              <option value="builtin">内置搜索</option>
              <option value="external">外部搜索</option>
            </select>
          </div>
          <div class="form-group">
            <label>输入价格 (每千 token)</label>
            <input type="number" step="0.0001" v-model.number="form.input_price_per_1k" />
          </div>
          <div class="form-group">
            <label>输出价格 (每千 token)</label>
            <input type="number" step="0.0001" v-model.number="form.output_price_per_1k" />
          </div>
          <div class="form-group">
            <label>货币</label>
            <select v-model="form.currency">
              <option value="CNY">CNY</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <div class="form-group">
            <label>特点标签 (逗号分隔)</label>
            <input v-model="characteristicsInput" placeholder="例如: 擅长报告写作, 搜索能力强" />
          </div>
          <div class="form-group">
            <label>备注</label>
            <textarea v-model="form.notes" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>
              <input type="checkbox" v-model="form.is_active" />
              启用
            </label>
          </div>
          <div class="form-actions">
            <button type="button" @click="closeDialog" class="btn btn-secondary">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? '提交中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import type { ModelProfile, ModelProfileCreate, ModelProfileUpdate } from '../types'
import {
  listModelProfiles,
  createModelProfile,
  updateModelProfile,
  deactivateModelProfile,
  activateModelProfile,
  refreshModelStats
} from '../api/platform'

const models = ref<ModelProfile[]>([])
const loading = ref(false)
const showActiveOnly = ref(true)
const showAddDialog = ref(false)
const editingModel = ref<ModelProfile | null>(null)
const submitting = ref(false)

const form = ref<ModelProfileCreate>({
  provider: '',
  name: '',
  display_name: '',
  api_base: '',
  api_key_env: '',
  supports_search: false,
  search_mode: 'builtin',
  input_price_per_1k: 0,
  output_price_per_1k: 0,
  currency: 'CNY',
  characteristics: [],
  is_active: true,
  notes: ''
})

const characteristicsInput = computed({
  get: () => (form.value.characteristics || []).join(', '),
  set: (value: string) => {
    form.value.characteristics = value.split(',').map(s => s.trim()).filter(s => s)
  }
})

async function loadModels() {
  loading.value = true
  try {
    models.value = await listModelProfiles(showActiveOnly.value)
  } catch (error) {
    console.error('加载模型列表失败:', error)
    alert('加载模型列表失败')
  } finally {
    loading.value = false
  }
}

function editModel(model: ModelProfile) {
  editingModel.value = model
  form.value = {
    provider: model.provider,
    name: model.name,
    display_name: model.display_name,
    api_base: model.api_base,
    api_key_env: model.api_key_env,
    supports_search: model.supports_search,
    search_mode: model.search_mode,
    input_price_per_1k: model.input_price_per_1k,
    output_price_per_1k: model.output_price_per_1k,
    currency: model.currency,
    characteristics: [...model.characteristics],
    is_active: model.is_active,
    notes: model.notes
  }
}

function closeDialog() {
  showAddDialog.value = false
  editingModel.value = null
  form.value = {
    provider: '',
    name: '',
    display_name: '',
    api_base: '',
    api_key_env: '',
    supports_search: false,
    search_mode: 'builtin',
    input_price_per_1k: 0,
    output_price_per_1k: 0,
    currency: 'CNY',
    characteristics: [],
    is_active: true,
    notes: ''
  }
}

async function submitForm() {
  submitting.value = true
  try {
    if (editingModel.value) {
      const updateData: ModelProfileUpdate = { ...form.value }
      await updateModelProfile(editingModel.value.id, updateData)
      alert('模型更新成功')
    } else {
      await createModelProfile(form.value)
      alert('模型添加成功')
    }
    closeDialog()
    await loadModels()
  } catch (error) {
    console.error('保存模型失败:', error)
    alert('保存模型失败')
  } finally {
    submitting.value = false
  }
}

async function deactivateModel(modelId: number) {
  if (!confirm('确定要禁用此模型吗？')) return
  try {
    await deactivateModelProfile(modelId)
    await loadModels()
  } catch (error) {
    console.error('禁用模型失败:', error)
    alert('禁用模型失败')
  }
}

async function activateModel(modelId: number) {
  try {
    await activateModelProfile(modelId)
    await loadModels()
  } catch (error) {
    console.error('启用模型失败:', error)
    alert('启用模型失败')
  }
}

async function refreshStats(modelId: number) {
  try {
    await refreshModelStats(modelId)
    await loadModels()
    alert('统计已刷新')
  } catch (error) {
    console.error('刷新统计失败:', error)
    alert('刷新统计失败')
  }
}

onMounted(() => {
  loadModels()
})
</script>

<style scoped>
.model-library {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.filters {
  margin-bottom: 20px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #666;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.model-table {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}

th {
  background: #f5f5f5;
  font-weight: 600;
}

.characteristics {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  background: #e3f2fd;
  color: #1976d2;
  border-radius: 12px;
  font-size: 12px;
}

.score {
  font-weight: 600;
  color: #2e7d32;
}

.text-muted {
  color: #999;
  font-size: 12px;
}

.badge-success {
  display: inline-block;
  padding: 2px 8px;
  background: #c8e6c9;
  color: #2e7d32;
  border-radius: 4px;
  font-size: 12px;
}

.badge-warning {
  display: inline-block;
  padding: 2px 8px;
  background: #fff3e0;
  color: #e65100;
  border-radius: 4px;
  font-size: 12px;
}

.badge-secondary {
  display: inline-block;
  padding: 2px 8px;
  background: #f5f5f5;
  color: #666;
  border-radius: 4px;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-sm {
  padding: 4px 12px;
  font-size: 12px;
}

.btn-primary {
  background: #1976d2;
  color: white;
}

.btn-primary:hover {
  background: #1565c0;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

.btn-secondary:hover {
  background: #d0d0d0;
}

.btn-success {
  background: #2e7d32;
  color: white;
}

.btn-success:hover {
  background: #1b5e20;
}

.btn-warning {
  background: #e65100;
  color: white;
}

.btn-warning:hover {
  background: #bf360c;
}

.btn-info {
  background: #0277bd;
  color: white;
}

.btn-info:hover {
  background: #01579b;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal h2 {
  margin-top: 0;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
}

.form-group input[type="text"],
.form-group input[type="number"],
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-group input[type="checkbox"] {
  margin-right: 8px;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}
</style>
