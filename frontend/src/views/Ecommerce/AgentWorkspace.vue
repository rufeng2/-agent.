<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>运营 Agent</h1>
        <p>输入经营问题，查看意图识别、工具调用轨迹、数据证据和建议动作。</p>
      </div>
    </div>

    <div class="panel agent-layout">
      <div class="agent-overview">
        <div><span>1</span><strong>提出经营问题</strong><small>选择示例或输入问题</small></div>
        <div><span>2</span><strong>专家协作分析</strong><small>主管分派专业 Agent</small></div>
        <div><span>3</span><strong>风险复核</strong><small>检查证据与动作风险</small></div>
        <div><span>4</span><strong>形成运营建议</strong><small>输出结论和下一步动作</small></div>
      </div>
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
      <div v-if="loading" class="job-progress"><div><strong>{{ jobLabel }}</strong><small>任务编号 {{ jobId.slice(0, 8) }}</small></div><el-button type="danger" plain @click="cancelJob">取消任务</el-button></div>

      <el-empty v-if="!analysis" description="选择一个问题开始分析" />
      <template v-else>
        <div class="result-heading"><span>分析结论</span><h2>{{ analysis.summary }}</h2></div>
        <div class="mode-row"><el-tag :type="analysis.execution_mode === 'llm' ? 'success' : 'warning'">{{ modeLabel(analysis.execution_mode) }}</el-tag><span v-if="analysis.fallback_reason">模型不可用时已自动切换稳定分析模式</span></div>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="分析场景">{{ intentLabel(analysis.intent) }}</el-descriptions-item>
          <el-descriptions-item label="风险等级"><el-tag :type="riskType(analysis.risk_level)">{{ riskLabel(analysis.risk_level) }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="结论置信度">{{ Math.round(analysis.confidence * 100) }}%</el-descriptions-item>
        </el-descriptions>

        <h3>多 Agent 协作流程</h3>
        <div v-if="analysis.agent_trace?.length" class="agent-collaboration">
          <article v-for="(agent, index) in analysis.agent_trace" :key="agent.agent" class="agent-step"><span>{{ index + 1 }}</span><div><strong>{{ agentLabel(agent.agent) }}</strong><small>{{ agentDescription(agent.agent) }}</small></div><el-tag type="success" effect="plain">{{ statusLabel(agent.status) }}</el-tag></article>
        </div>
        <h3>分析工具与结果</h3>
        <div class="trace-list">
          <article v-for="(step, index) in analysis.tool_trace" :key="step.tool_name" class="trace-step">
            <span>{{ index + 1 }}</span>
            <div>
              <strong>{{ step.step_title || step.tool_name }}</strong>
              <small>{{ toolLabel(step.tool_name) }}</small>
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
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"

const prompts = ["昨天 GMV 为什么下降？", "哪些商品适合参加大促？", "哪些广告计划 ROI 太低？", "哪些商品存在库存风险？"]
const question = ref(prompts[0])
const loading = ref(false)
const analysis = ref<any>(null)
const jobId = ref("")
const jobStatus = ref("")
let pollTimer: number | undefined
const sessionId = ref("")
const sessions = ref<any[]>([])
const messages = ref<any[]>([])
const jobLabel = computed(() => ({ queued: "任务已进入队列", running: "专家正在分析", created: "正在创建任务" } as Record<string, string>)[jobStatus.value] || "正在处理")
const agentNames: Record<string, string> = { supervisor: "运营主管 Agent", data_analyst: "数据分析 Agent", product: "商品运营 Agent", customer: "客户运营 Agent", campaign: "活动策略 Agent", risk_reviewer: "风险审核 Agent", report_writer: "报告生成 Agent" }
const agentDescriptions: Record<string, string> = { supervisor: "识别问题并分配专家", data_analyst: "分析 GMV、漏斗与趋势", product: "分析商品、库存与竞品", customer: "分析客户分层与复购", campaign: "评估活动与运营方案", risk_reviewer: "复核证据与动作风险", report_writer: "合并专家结论" }
const toolNames: Record<string, string> = { get_kpi_snapshot: "经营指标快照", explain_gmv_attribution: "GMV 变化归因", detect_anomalies: "经营异常检测", rank_products: "商品经营排序", analyze_conversion_funnel: "转化漏斗分析", analyze_customer_rfm: "客户 RFM 分层", analyze_campaign_effect: "活动效果分析", analyze_competitor_price: "竞品价格分析", forecast_gmv: "GMV 趋势预测", generate_campaign_plan: "活动方案生成" }
const intentNames: Record<string, string> = { business_diagnosis: "综合经营诊断", campaign_planning: "活动策略", ad_review: "广告投放复盘", inventory_risk: "库存风险", customer_analysis: "客户分析", competitor_analysis: "竞品分析", funnel_analysis: "转化漏斗" }
const agentLabel = (value: string) => agentNames[value] || value
const agentDescription = (value: string) => agentDescriptions[value] || "执行专业分析"
const toolLabel = (value: string) => toolNames[value] || value
const intentLabel = (value: string) => intentNames[value] || value
const statusLabel = (value: string) => ({ completed: "已完成", passed: "审核通过", insufficient_evidence: "证据不足" } as Record<string, string>)[value] || value
const riskLabel = (value: string) => ({ high: "高风险", medium: "中风险", low: "低风险" } as Record<string, string>)[value] || value
const riskType = (value: string) => value === "high" ? "danger" : value === "medium" ? "warning" : "success"
const modeLabel = (value: string) => ({ llm: "大模型增强分析", multi_agent_deterministic: "多 Agent 稳定分析", deterministic_fallback: "稳定降级分析", deterministic: "规则分析" } as Record<string, string>)[value] || value

async function loadSessions() { sessions.value = (await ecommerceAPI.sessions()).data.data }
async function selectSession() { if (!sessionId.value) return; const data=(await ecommerceAPI.sessionDetail(sessionId.value)).data.data; messages.value=data.messages }
function newSession(){ sessionId.value=""; messages.value=[]; analysis.value=null }

async function analyze() {
  if (!question.value.trim()) return
  loading.value = true
  try {
    const created = (await ecommerceAPI.createJob(question.value, sessionId.value)).data.data
    jobId.value = created.job_id
    jobStatus.value = created.status
    analysis.value = await waitForJob(created.job_id)
    sessionId.value = analysis.value.session_id
    await Promise.all([loadSessions(), selectSession()])
  } catch {
    ElMessage.error("Agent 分析失败")
  } finally {
    loading.value = false
  }
}
async function waitForJob(id: string): Promise<any> {
  while (true) {
    const current = (await ecommerceAPI.jobStatus(id)).data.data
    jobStatus.value = current.status
    if (current.status === "completed") return current.result
    if (current.status === "failed" || current.status === "cancelled") throw new Error(current.error || current.status)
    await new Promise(resolve => { pollTimer = window.setTimeout(resolve, 700) })
  }
}
async function cancelJob() {
  if (!jobId.value) return
  await ecommerceAPI.cancelJob(jobId.value)
  jobStatus.value = "cancelled"
  loading.value = false
  if (pollTimer) window.clearTimeout(pollTimer)
}
onMounted(loadSessions)
</script>

<style scoped>
.agent-layout{padding:18px}.session-bar{display:flex;gap:8px;margin-bottom:12px}.session-bar .el-select{width:min(360px,70vw)}.message-history{max-height:220px;overflow:auto;margin-bottom:14px;padding:10px;background:#f7f9f8;border:1px solid var(--border);border-radius:6px}.message-history p{display:grid;grid-template-columns:54px 1fr;gap:8px;margin:6px 0;line-height:1.5}.message-history p.assistant strong{color:var(--success)}.mode-row{display:flex;align-items:center;gap:8px;margin:8px 0 14px;color:var(--ink-muted);font-size:12px}.question-bar{display:grid;grid-template-columns:1fr auto;gap:10px}.quick-prompts{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px}.agent-layout h2{font-size:18px;line-height:1.5}.agent-layout h3{margin:22px 0 10px;font-size:15px}.trace-list{display:grid;gap:10px}.trace-step{display:grid;grid-template-columns:32px 1fr;gap:12px;border:1px solid var(--border);border-radius:6px;padding:12px;background:#fff}.trace-step>span{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#2563eb;color:#fff;font-weight:700}.trace-step strong,.trace-step small,.trace-step code{display:block}.trace-step small{margin-top:2px;color:var(--ink-muted)}.trace-step p{margin:8px 0;color:var(--ink);line-height:1.5}.trace-step code{white-space:normal;word-break:break-word;color:var(--ink-muted);font-size:12px}
.agent-overview{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid var(--border)}.agent-overview>div{display:grid;grid-template-columns:28px 1fr;column-gap:9px;align-items:center}.agent-overview span{grid-row:1/3;display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#e8f0fe;color:#1d4ed8;font-weight:700}.agent-overview strong{font-size:13px}.agent-overview small{color:var(--ink-muted)}.job-progress{display:flex;align-items:center;justify-content:space-between;margin:10px 0;padding:12px 14px;border-left:3px solid #2563eb;background:#f5f8ff}.job-progress strong,.job-progress small{display:block}.job-progress small{margin-top:3px;color:var(--ink-muted)}.result-heading{margin-top:18px;padding:16px;border-left:4px solid #16a34a;background:#f4faf6}.result-heading>span{color:#15803d;font-size:12px;font-weight:700}.result-heading h2{margin:6px 0 0}.agent-collaboration{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}.agent-step{display:grid;grid-template-columns:28px 1fr auto;gap:9px;align-items:center;padding:12px;border:1px solid var(--border);border-radius:6px;background:#fff}.agent-step>span{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#111827;color:#fff;font-size:12px}.agent-step strong,.agent-step small{display:block}.agent-step small{margin-top:3px;color:var(--ink-muted);font-size:11px}@media(max-width:760px){.agent-overview{grid-template-columns:1fr 1fr}.agent-step{grid-template-columns:28px 1fr}.agent-step .el-tag{grid-column:2}}
.agent-step{grid-template-columns:28px 1fr}.agent-step .el-tag{grid-column:2;width:max-content}
</style>
