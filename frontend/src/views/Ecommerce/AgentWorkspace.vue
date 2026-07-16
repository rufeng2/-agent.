<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>运营 Agent</h1>
        <p>输入经营问题，查看意图识别、工具调用轨迹、数据证据和建议动作。</p>
      </div>
    </div>

    <div class="panel agent-layout">
      <div class="session-bar">
        <el-select v-model="sessionId" clearable placeholder="新会话" @change="selectSession">
          <el-option v-for="item in sessions" :key="item.id" :label="item.title" :value="item.id" />
        </el-select>
        <el-button @click="newSession">新建会话</el-button>
      </div>
      <div v-if="messages.length" class="message-history">
        <p v-for="item in messages" :key="item.id" :class="item.role"><strong>{{ item.role === 'user' ? '我' : 'Agent' }}</strong>{{ item.content }}</p>
      </div>
      <div class="question-bar">
        <el-input v-model="question" size="large" placeholder="例如：昨天 GMV 为什么下降？" @keyup.enter="analyze" />
        <el-button type="primary" size="large" :loading="loading" @click="analyze">分析</el-button>
      </div>
      <div class="quick-prompts">
        <el-button v-for="item in prompts" :key="item" @click="question = item; analyze()">{{ item }}</el-button>
      </div>

      <el-empty v-if="!analysis" description="选择一个问题开始分析" />
      <template v-else>
        <h2>{{ analysis.summary }}</h2>
        <div class="mode-row"><el-tag :type="analysis.execution_mode === 'llm' ? 'success' : 'warning'">{{ analysis.execution_mode }}</el-tag><span v-if="analysis.fallback_reason">{{ analysis.fallback_reason }}</span></div>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="意图">{{ analysis.intent }}</el-descriptions-item>
          <el-descriptions-item label="风险">{{ analysis.risk_level }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ analysis.confidence }}</el-descriptions-item>
        </el-descriptions>

        <h3>Agent 执行轨迹</h3>
        <div class="trace-list">
          <article v-for="(step, index) in analysis.tool_trace" :key="step.tool_name" class="trace-step">
            <span>{{ index + 1 }}</span>
            <div>
              <strong>{{ step.step_title || step.tool_name }}</strong>
              <small>{{ step.tool_name }}</small>
              <p>{{ step.output_summary }}</p>
              <code>{{ JSON.stringify(step.input) }}</code>
            </div>
          </article>
        </div>

        <h3>数据证据</h3>
        <el-table :data="analysis.evidence">
          <el-table-column prop="label" label="指标" />
          <el-table-column prop="value" label="当前值" />
          <el-table-column prop="baseline" label="基准" />
          <el-table-column prop="rule" label="触发规则" />
        </el-table>

        <h3>建议动作</h3>
        <el-table :data="analysis.recommendations">
          <el-table-column prop="title" label="建议" min-width="180" />
          <el-table-column prop="risk_level" label="风险" width="100" />
          <el-table-column prop="expected_impact" label="预期影响" />
        </el-table>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"

const prompts = ["昨天 GMV 为什么下降？", "哪些商品适合参加大促？", "哪些广告计划 ROI 太低？", "哪些商品存在库存风险？"]
const question = ref(prompts[0])
const loading = ref(false)
const analysis = ref<any>(null)
const sessionId = ref("")
const sessions = ref<any[]>([])
const messages = ref<any[]>([])

async function loadSessions() { sessions.value = (await ecommerceAPI.sessions()).data.data }
async function selectSession() { if (!sessionId.value) return; const data=(await ecommerceAPI.sessionDetail(sessionId.value)).data.data; messages.value=data.messages }
function newSession(){ sessionId.value=""; messages.value=[]; analysis.value=null }

async function analyze() {
  if (!question.value.trim()) return
  loading.value = true
  try {
    analysis.value = (await ecommerceAPI.analyze(question.value, sessionId.value)).data.data
    sessionId.value = analysis.value.session_id
    await Promise.all([loadSessions(), selectSession()])
  } catch {
    ElMessage.error("Agent 分析失败")
  } finally {
    loading.value = false
  }
}
onMounted(loadSessions)
</script>

<style scoped>
.agent-layout{padding:18px}.session-bar{display:flex;gap:8px;margin-bottom:12px}.session-bar .el-select{width:min(360px,70vw)}.message-history{max-height:220px;overflow:auto;margin-bottom:14px;padding:10px;background:#f7f9f8;border:1px solid var(--border);border-radius:6px}.message-history p{display:grid;grid-template-columns:54px 1fr;gap:8px;margin:6px 0;line-height:1.5}.message-history p.assistant strong{color:var(--success)}.mode-row{display:flex;align-items:center;gap:8px;margin:8px 0 14px;color:var(--ink-muted);font-size:12px}.question-bar{display:grid;grid-template-columns:1fr auto;gap:10px}.quick-prompts{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px}.agent-layout h2{font-size:18px;line-height:1.5}.agent-layout h3{margin:22px 0 10px;font-size:15px}.trace-list{display:grid;gap:10px}.trace-step{display:grid;grid-template-columns:32px 1fr;gap:12px;border:1px solid var(--border);border-radius:6px;padding:12px;background:#fff}.trace-step>span{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#2563eb;color:#fff;font-weight:700}.trace-step strong,.trace-step small,.trace-step code{display:block}.trace-step small{margin-top:2px;color:var(--ink-muted)}.trace-step p{margin:8px 0;color:var(--ink);line-height:1.5}.trace-step code{white-space:normal;word-break:break-word;color:var(--ink-muted);font-size:12px}
</style>
