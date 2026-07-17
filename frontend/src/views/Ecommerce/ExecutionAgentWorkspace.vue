<template>
  <section class="assistant-page">
    <header class="assistant-header">
      <div><h1>电商运营执行助手</h1><p>对话下达任务，确认后由多 Agent 调用业务工具执行。</p></div>
      <div class="runtime-tags"><el-tag :type="mcpStatus==='ready'?'success':mcpStatus==='unavailable'?'danger':'info'" effect="plain">MCP {{ mcpStatus }}</el-tag><el-tag type="warning" effect="plain">沙箱</el-tag></div>
    </header>
    <div class="conversation-shell">
      <aside class="session-list">
        <div class="section-heading"><h2>会话</h2><el-button text circle title="刷新" @click="loadConversations"><el-icon><Refresh /></el-icon></el-button></div>
        <el-button class="new-chat" @click="newChat">新建会话</el-button>
        <el-empty v-if="!conversations.length" description="暂无会话" />
        <button v-for="item in conversations" :key="item.id" type="button" class="task-item" :class="{active:sessionId===item.id}" @click="openConversation(item.id)">
          <span>历史会话</span><strong>{{ item.title }}</strong><small>{{ formatTime(item.updated_at) }}</small>
        </button>
      </aside>
      <main class="conversation-main">
        <div class="message-stream">
        <div v-if="!messages.length && !task" class="welcome-message">
          <div class="assistant-avatar">AI</div><div><h2>需要我执行什么运营任务？</h2><p>可以生成推广文案、调整商品价格、上下架商品或创建营销活动。</p></div>
        </div>
        <div v-for="(item,index) in messages" :key="index" class="message" :class="item.role==='user'?'user-message':'assistant-message'">
          <div v-if="item.role==='assistant'" class="assistant-avatar">AI</div><div class="message-body"><small>{{ item.role==='user'?'你':'运营执行助手' }}</small><p>{{ item.content }}</p></div>
        </div>
        <section v-if="report" class="message assistant-message"><div class="assistant-avatar">AI</div><div class="message-body analysis-report">
          <div class="receipt-heading"><div><span>分析报告</span><h3>{{ report.title }}</h3></div><el-tag type="success">{{ report.generation_mode }}</el-tag></div>
          <small v-if="report.context_stats" class="context-stats">上下文 GSSC：选中 {{ report.context_stats.selected }}/{{ report.context_stats.gathered }} 条 · {{ report.context_stats.used_tokens }}/{{ report.context_stats.available_tokens }} tokens</small>
          <p>{{ report.summary }}</p>
          <section v-if="report.autonomous_run" class="autonomous-run">
            <div class="kpi-strip"><div><span>运行轮次</span><strong>{{ report.autonomous_run.iteration }}</strong></div><div><span>实际变化</span><strong>{{ report.autonomous_run.evaluation.actual_change_pct }}%</strong></div><div><span>目标变化</span><strong>{{ report.autonomous_run.evaluation.target_change_pct }}%</strong></div><div><span>沙箱成本</span><strong>¥{{ report.autonomous_run.spent }}</strong></div></div>
            <h4>动态任务计划 · v{{ report.autonomous_run.plan.version }}</h4>
            <div class="plan-steps"><div v-for="step in report.autonomous_run.plan.steps" :key="step.id"><span>{{ step.status==='completed'?'✓':'·' }}</span><strong>{{ step.agent }}</strong><small>{{ step.tool }}<template v-if="step.depends_on.length"> · 依赖 {{ step.depends_on.join(', ') }}</template></small></div></div>
            <h4 v-if="report.autonomous_run.reflections.length">Critic 反思与重规划</h4>
            <div class="reflection-item" v-for="item in report.autonomous_run.reflections" :key="item.iteration"><strong>第 {{ item.iteration }} 轮 · {{ item.decision }} · 综合 {{ item.overall_score }}</strong><p>{{ item.reason }}</p><div class="score-row"><span v-for="(score,key) in item.scores" :key="key">{{ key }} {{ score }}</span></div><small>下一步：{{ item.next_change }}</small></div>
            <div class="trace-stats">Trace：{{ report.autonomous_run.trace_stats.events }} 事件 · {{ report.autonomous_run.trace_stats.steps }} 步骤 · {{ report.autonomous_run.trace_stats.replans }} 次重规划 · {{ report.autonomous_run.trace_stats.errors }} 错误</div>
            <div v-if="report.autonomous_run.status==='succeeded'" class="memory-note">成功经验已写入情景、SOP、商品语义和用户偏好记忆，可供后续同类目标召回。</div>
            <el-button v-if="report.autonomous_run.status==='failed'" type="primary" :loading="executing" @click="resumeAutonomous">从检查点恢复</el-button>
          </section>
          <div class="report-columns"><div><h4>关键发现</h4><ul><li v-for="item in report.findings" :key="item">{{ item }}</li></ul></div><div><h4>运营机会</h4><ul><li v-for="item in report.opportunities" :key="item">{{ item }}</li></ul></div></div>
          <h4>建议动作</h4><ol><li v-for="item in report.actions" :key="item">{{ item }}</li></ol>
          <details class="evidence-list"><summary>查看数据证据（{{ report.evidence?.length || 0 }}）</summary><div v-for="item in report.evidence" :key="`${item.metric}-${item.source}`"><strong>{{ item.metric }}</strong><span>{{ evidenceValue(item.value) }}</span><small>{{ item.source }} · {{ item.period }} · 样本 {{ item.sample_size }}</small></div></details>
        </div></section>
        <template v-if="task">
          <div class="message assistant-message"><div class="assistant-avatar">AI</div><div class="message-body">
            <div class="message-heading"><strong>已完成任务规划</strong><el-tag :type="statusType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag></div>
            <p v-if="task.state?.product">我识别到目标商品为 <b>{{ task.state.product.name }}（{{ task.state.product.product_id }}）</b>，将执行“{{ actionLabel(task.state.action_type) }}”。</p>
            <div v-if="task.state?.product" class="plan-facts"><span>风险：{{ task.state.risk_level==='high'?'高':'中' }}</span><span>审批：{{ task.state.required_approval_role || 'user' }}</span><span>{{ task.events.length }} 个执行节点</span></div>
            <details class="agent-details"><summary>查看多 Agent 执行轨迹</summary>
              <div class="agent-timeline"><article v-for="(event,index) in task.events" :key="`${event.type}-${index}`"><span>{{ index+1 }}</span><div><strong>{{ event.agent }}</strong><p>{{ event.detail }}</p></div><small>{{ eventTypeLabel(event.type) }}</small></article></div>
            </details>
          </div>
          </div>
          <section v-if="task.status==='waiting_approval'" class="message assistant-message"><div class="assistant-avatar">AI</div><div class="message-body approval-gate">
            <div><span>等待人工批准</span><h3>{{ task.state.approval_reason }}</h3><p>{{ parameterSummary(task.state) }}</p></div>
            <el-button type="primary" size="large" :loading="executing" @click="approve">批准并执行</el-button>
          </div></section>
          <section v-if="task.result?.status==='completed'" class="message assistant-message"><div class="assistant-avatar">AI</div><div class="message-body receipt">
            <div class="receipt-heading"><div><span>执行回执</span><h3>{{ task.result.action_type==='content_generation'?'推广文案已生成':'业务工具已完成写入' }}</h3></div><el-tag type="success">{{ task.result.environment }}</el-tag></div>
            <div v-if="['price_update','product_publish','product_unpublish','composite'].includes(task.result.action_type)" class="before-after">
              <div><span>执行前</span><strong>{{ snapshot(task.result.before,task.result.action_type) }}</strong></div>
              <div><span>执行后</span><strong>{{ snapshot(task.result.after,task.result.action_type) }}</strong></div>
            </div>
            <div v-if="task.result.action_type==='marketing_plan'" class="campaign-result"><span>已创建推广活动</span><strong>{{ task.result.campaign.name }}</strong><p>日预算 ¥{{ task.result.campaign.daily_budget }} · 目标 ACOS {{ task.result.campaign.target_acos_pct }}%</p></div>
            <article v-if="task.result.action_type==='content_generation'" class="copy-result">
              <div class="copy-meta"><span>{{ task.result.copy.channel }}推广文案</span><el-tag size="small" :type="task.result.copy.generation_mode==='llm'?'success':'warning'">{{ task.result.copy.generation_mode==='llm'?'DeepSeek 生成':'模板降级' }}</el-tag></div>
              <h4>{{ task.result.copy.headline }}</h4><p>{{ task.result.copy.body }}</p>
              <ul><li v-for="point in task.result.copy.selling_points" :key="point">{{ point }}</li></ul>
              <strong class="copy-cta">{{ task.result.copy.cta }}</strong><small>{{ task.result.copy.hashtags.join(' ') }}</small>
            </article>
            <div v-if="task.result.mcp" class="mcp-receipt"><span>MCP 工具调用</span><strong>{{ task.result.mcp.server }} · {{ task.result.mcp.tool || task.result.mcp.tools?.join(' + ') }}</strong><small>{{ task.result.mcp.transport }}</small></div>
            <div v-if="task.result.steps" class="dag-steps"><strong v-for="step in task.result.steps" :key="step.id">{{ step.id }} · {{ step.status }}</strong></div>
            <el-button v-if="task.status==='completed' && ['price_update','product_publish','product_unpublish'].includes(task.result.action_type)" :loading="executing" @click="rollback">回滚本次变更</el-button>
          </div></section>
          <el-alert v-if="task.error" class="task-error" type="error" :title="task.error" show-icon :closable="false" />
        </template>
        </div>
        <footer class="composer">
          <div class="examples"><button v-for="item in examples" :key="item" type="button" @click="goal=item">{{ item }}</button></div>
          <div class="command-input"><el-input v-model="goal" size="large" placeholder="输入运营任务，例如：给便携榨汁杯写一篇小红书推广文案" @keyup.enter="createTask" /><el-button type="primary" size="large" :loading="creating" @click="createTask">创建并运行</el-button></div>
          <small>{{ awaitingClarification?'请补充上面的问题，我会继续当前任务':'分析任务直接返回证据报告，业务写操作会在执行前请求确认' }}</small>
        </footer>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus/es/components/message/index"
import { ElMessageBox } from "element-plus/es/components/message-box/index"
import { Refresh } from "@element-plus/icons-vue"
import { ecommerceAPI } from "@/api/client"

const examples=["给便携榨汁杯做一个小红书推广文案","把轻量跑步鞋价格调整到 269 元","下架商品 P003","给轻量跑步鞋创建新品冷启动推广活动"]
const goal=ref(examples[0]),tasks=ref<any[]>([]),task=ref<any>(null),creating=ref(false),executing=ref(false)
const conversations=ref<any[]>([]),sessionId=ref<string>(),messages=ref<any[]>([]),report=ref<any>(null),awaitingClarification=ref(false)
const mcpStatus=ref("checking")
const message=(error:any)=>error?.response?.data?.detail||error?.message||"请求失败"
const statusLabel=(value:string)=>({planning:"规划中",waiting_approval:"待审批",running:"执行中",completed:"已完成",failed:"失败",rolled_back:"已回滚"} as any)[value]||value
const statusType=(value:string)=>value==="completed"?"success":value==="failed"?"danger":value==="waiting_approval"?"warning":"info"
const actionLabel=(value:string)=>({price_update:"调整价格",product_publish:"商品上架",product_unpublish:"商品下架",marketing_plan:"创建营销活动",content_generation:"生成推广文案",composite:"复合执行任务"} as any)[value]||"待识别"
const eventTypeLabel=(value:string)=>({task_planned:"任务规划",dag_planned:"DAG 规划",context_loaded:"读取数据",mcp_tool_called:"MCP 读取",policy_validated:"策略校验",change_prepared:"准备变更",campaign_prepared:"生成活动",copy_generated:"生成文案",approval_required:"审批断点",approved:"恢复执行",task_completed:"工具回执",content_delivered:"文案交付",dag_completed:"DAG 完成",mcp_tool_completed:"MCP 回执",task_rolled_back:"回滚完成",mcp_rollback_completed:"MCP 回滚"} as any)[value]||value
function parameterSummary(state:any){if(["price_update","composite"].includes(state.action_type)){const price=`价格从 ¥${state.parameters.old_price} 调整到 ¥${state.parameters.new_price}，幅度 ${state.parameters.change_pct}%`;return state.action_type==="composite"?`${price}；随后创建“${state.parameters.campaign.name}”推广活动`:price}if(state.action_type==="marketing_plan")return `创建“${state.parameters.campaign.name}”，日预算 ¥${state.parameters.campaign.daily_budget}`;if(state.action_type==="content_generation")return `审核“${state.parameters.copy.headline}”及正文、卖点和 CTA，通过后交付`;return `商品状态将改为 ${state.parameters.listing_status}`}
function snapshot(value:any,type:string){return ["price_update","composite"].includes(type)?`¥${value.price} · 版本 ${value.catalog_version}`:`${value.listing_status==='listed'?'已上架':'已下架'} · 版本 ${value.catalog_version}`}
async function loadTasks(){tasks.value=(await ecommerceAPI.executionTasks()).data.data;if(task.value)task.value=tasks.value.find((item:any)=>item.id===task.value.id)||task.value}
async function loadConversations(){conversations.value=(await ecommerceAPI.conversations()).data.data}
async function openConversation(id:string){const data=(await ecommerceAPI.conversation(id)).data.data;sessionId.value=id;task.value=null;report.value=null;messages.value=data.messages.map((item:any)=>{if(item.role==='assistant'){try{const parsed=JSON.parse(item.content);if(parsed.evidence){report.value=parsed;return null}}catch{}}return {role:item.role,content:item.content}}).filter(Boolean)}
function newChat(){sessionId.value=undefined;messages.value=[];report.value=null;task.value=null;awaitingClarification.value=false;goal.value=''}
async function loadMcpStatus(){for(let attempt=0;attempt<2;attempt++){try{mcpStatus.value=(await ecommerceAPI.mcpStatus()).data.data.status;return}catch{if(!attempt)await new Promise(resolve=>setTimeout(resolve,800))}}mcpStatus.value="unavailable"}
async function createTask(){const input=goal.value.trim();if(!input)return;creating.value=true;messages.value.push({role:'user',content:input});goal.value='';try{const reply=(await ecommerceAPI.sendConversationMessage(input,sessionId.value)).data.data;sessionId.value=reply.session_id;messages.value.push({role:'assistant',content:reply.message});awaitingClarification.value=reply.status==='needs_clarification';report.value=reply.report&&Object.keys(reply.report).length?reply.report:null;task.value=reply.task||null;await Promise.all([loadConversations(),loadTasks()]);if(reply.status==='waiting_approval')ElMessage.success("执行计划已生成，请审批")}catch(error:any){messages.value.push({role:'assistant',content:message(error)});ElMessage.error(message(error))}finally{creating.value=false}}
async function approve(){await ElMessageBox.confirm("批准后将立即修改模拟业务系统，是否继续？","执行确认",{type:"warning",confirmButtonText:"批准并执行"});executing.value=true;try{task.value=(await ecommerceAPI.approveExecutionTask(task.value.id,task.value.version,"已核对执行参数")).data.data;await loadTasks();ElMessage.success("任务执行完成")}catch(error:any){ElMessage.error(message(error))}finally{executing.value=false}}
async function rollback(){await ElMessageBox.confirm("将业务状态恢复到本任务执行前，是否继续？","回滚确认",{type:"warning"});executing.value=true;try{task.value=(await ecommerceAPI.rollbackExecutionTask(task.value.id,task.value.version)).data.data;await loadTasks();ElMessage.success("变更已回滚")}catch(error:any){ElMessage.error(message(error))}finally{executing.value=false}}
async function resumeAutonomous(){executing.value=true;try{const result=(await ecommerceAPI.resumeAutonomousTask(report.value.autonomous_run.task_id)).data.data;report.value.autonomous_run=result;ElMessage.success("自主任务已从检查点恢复")}catch(error:any){ElMessage.error(message(error))}finally{executing.value=false}}
function formatTime(value:string){return new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})}
function evidenceValue(value:any){return typeof value==='object'?JSON.stringify(value):String(value)}
onMounted(()=>Promise.all([loadTasks(),loadMcpStatus(),loadConversations()]))
</script>

<style scoped>
.command-band{padding:18px;margin-bottom:16px;border:1px solid var(--border);background:#fff}.command-input{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px}.examples{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.examples button{padding:8px 10px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--ink-muted);cursor:pointer}.examples button:hover{border-color:#2563eb;color:#1d4ed8}.workspace-grid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:16px}.task-list,.task-detail{padding:16px}.section-heading,.task-title,.receipt-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.section-heading h2,.task-title h2{margin:0}.section-heading h2{font-size:16px}.task-item{display:grid;width:100%;gap:5px;margin-top:8px;padding:11px;text-align:left;border:1px solid var(--border);border-radius:5px;background:#fff;cursor:pointer}.task-item.active{border-color:#2563eb;background:#f5f8ff}.task-item span,.task-item small,.task-title span,.change-summary span,.approval-gate span,.receipt span{color:var(--ink-muted);font-size:12px}.task-item strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-title h2{margin-top:5px;font-size:18px}.change-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.change-summary>div,.before-after>div{padding:12px;border:1px solid var(--border)}.change-summary strong,.change-summary span,.before-after strong,.before-after span{display:block}.change-summary strong,.before-after strong{margin-top:5px}.task-detail h3{font-size:15px}.agent-timeline{display:grid;gap:8px}.agent-timeline article{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:10px;align-items:center;padding:11px;border-bottom:1px solid var(--border)}.agent-timeline article>span{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#111827;color:#fff}.agent-timeline p{margin:4px 0 0;color:var(--ink-muted)}.agent-timeline small{color:#1d4ed8}.approval-gate{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:18px;padding:16px;border-left:4px solid #f59e0b;background:#fffbeb}.approval-gate h3{margin:5px 0}.approval-gate p{margin:0;color:var(--ink-muted)}.receipt{margin-top:18px;padding:16px;border-left:4px solid #16a34a;background:#f4faf6}.receipt h3{margin:5px 0}.before-after{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.campaign-result{margin:14px 0;padding:12px;border:1px solid #cce3d2;background:#fff}.campaign-result strong{display:block;margin-top:5px}.campaign-result p{margin-bottom:0;color:var(--ink-muted)}@media(max-width:900px){.workspace-grid{grid-template-columns:1fr}.task-list{max-height:260px;overflow:auto}.change-summary{grid-template-columns:1fr}}@media(max-width:600px){.command-input{grid-template-columns:1fr}.approval-gate{align-items:flex-start;flex-direction:column}.approval-gate .el-button{width:100%}.before-after{grid-template-columns:1fr}.agent-timeline article{grid-template-columns:28px minmax(0,1fr)}.agent-timeline small{grid-column:2}}
.mcp-receipt{display:flex;align-items:center;gap:10px;margin:12px 0;padding:10px;border:1px solid #cce3d2;background:#fff}.mcp-receipt span,.mcp-receipt small{color:var(--ink-muted);font-size:12px}.mcp-receipt small{margin-left:auto}@media(max-width:600px){.mcp-receipt{align-items:flex-start;flex-direction:column}.mcp-receipt small{margin-left:0}}
.dag-steps{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.dag-steps strong{padding:7px 9px;border:1px solid #cce3d2;background:#fff;color:#166534;font-size:12px}
.copy-result{margin:14px 0;padding:16px;border:1px solid #cce3d2;background:#fff}.copy-meta{display:flex;align-items:center;justify-content:space-between;gap:12px}.copy-result h4{margin:14px 0 8px;font-size:20px}.copy-result p{color:var(--ink-muted);line-height:1.8;white-space:pre-wrap}.copy-result ul{padding-left:20px;line-height:1.9}.copy-cta{display:inline-block;margin:8px 0;color:#166534}.copy-result small{display:block;color:var(--ink-muted);line-height:1.7}
.assistant-page{display:flex;flex-direction:column;height:100%;min-height:0;background:#fff}.assistant-header{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:76px;padding:14px 24px;border-bottom:1px solid var(--border)}.assistant-header h1{margin:0;font-size:20px}.assistant-header p{margin:4px 0 0;color:var(--ink-muted);font-size:12px}.runtime-tags{display:flex;gap:8px}.conversation-shell{display:grid;grid-template-columns:260px minmax(0,1fr);flex:1;min-height:0}.session-list{overflow:auto;padding:16px 12px;background:#f7f9f8;border-right:1px solid var(--border)}.new-chat{width:100%;margin:10px 0 4px}.conversation-main{display:flex;min-width:0;min-height:0;flex-direction:column;background:#fff}.message-stream{flex:1;overflow:auto;padding:28px max(28px,calc((100% - 840px)/2)) 40px}.welcome-message,.message{display:flex;gap:12px;margin-bottom:22px}.welcome-message{align-items:flex-start;padding-top:8vh}.welcome-message h2{margin:2px 0 6px;font-size:20px}.welcome-message p{margin:0;color:var(--ink-muted)}.assistant-avatar{display:grid;flex:0 0 34px;width:34px;height:34px;place-items:center;border-radius:50%;background:#17201c;color:#fff;font-size:11px;font-weight:700}.message-body{min-width:0;max-width:760px}.user-message{justify-content:flex-end}.user-message .message-body{padding:11px 15px;border-radius:8px 2px 8px 8px;background:#edf4ff}.user-message small{color:#47627f}.user-message p{margin:4px 0 0;line-height:1.65}.assistant-message .message-body{flex:1;padding:2px 0}.message-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.message-body>p{line-height:1.7;color:#495650}.plan-facts{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.plan-facts span{padding:5px 8px;border:1px solid var(--border);border-radius:4px;color:var(--ink-muted);font-size:12px}.agent-details{margin-top:12px;border-top:1px solid var(--border)}.agent-details summary{padding:11px 0;color:#2563eb;cursor:pointer;font-size:12px}.agent-timeline article{padding:10px 0}.approval-gate,.receipt{max-width:760px;margin:0;padding:16px;border:1px solid #ead9a8;border-left:4px solid #f59e0b;border-radius:5px;background:#fffbeb}.receipt{border-color:#cce3d2;border-left-color:#16a34a;background:#f4faf6}.approval-gate{display:flex;align-items:center;justify-content:space-between;gap:18px}.approval-gate h3{font-size:14px}.composer{padding:10px max(24px,calc((100% - 840px)/2)) 14px;background:#fff;border-top:1px solid var(--border);box-shadow:0 -8px 20px rgba(24,32,29,.04)}.composer .examples{margin:0 0 8px;overflow:hidden;flex-wrap:nowrap}.composer .examples button{flex:0 0 auto;padding:5px 8px;font-size:11px}.composer>small{display:block;margin-top:6px;color:var(--ink-muted);text-align:center;font-size:11px}.task-error{max-width:760px;margin-left:46px}.session-list .task-item{background:transparent}.session-list .task-item.active{background:#fff}
.analysis-report{width:100%;padding:18px;border:1px solid var(--border);border-left:4px solid #2563eb;border-radius:5px;background:#f8fafc}.analysis-report h3{margin:4px 0 0}.analysis-report h4{margin:16px 0 7px;font-size:13px}.analysis-report ul,.analysis-report ol{margin:0;padding-left:20px;line-height:1.8}.report-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px}.evidence-list{margin-top:16px;border-top:1px solid var(--border)}.evidence-list summary{padding:12px 0;color:#2563eb;cursor:pointer}.evidence-list>div{display:grid;grid-template-columns:150px minmax(0,1fr) auto;gap:10px;padding:8px 0;border-top:1px solid #edf0ee}.evidence-list small{color:var(--ink-muted)}
.autonomous-run{margin:16px 0;padding:14px;border:1px solid #bfd2f3;background:#fff}.kpi-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.kpi-strip>div{padding:10px;background:#f4f7fb}.kpi-strip span,.kpi-strip strong{display:block}.kpi-strip span{color:var(--ink-muted);font-size:11px}.kpi-strip strong{margin-top:5px;font-size:17px}.plan-steps{display:grid;gap:6px}.plan-steps>div{display:grid;grid-template-columns:24px 150px minmax(0,1fr);gap:8px;padding:8px;border-bottom:1px solid #edf0ee}.plan-steps>div>span{color:#16855b}.plan-steps small,.reflection-item small{color:var(--ink-muted)}.reflection-item{margin-top:8px;padding:10px;border-left:3px solid #f59e0b;background:#fffbeb}.reflection-item p{margin:5px 0}.memory-note{margin-top:12px;padding:9px;color:#166534;background:#eef8f2;font-size:12px}
.context-stats{display:block;margin-top:8px;color:var(--ink-muted)}.score-row{display:flex;flex-wrap:wrap;gap:6px;margin:7px 0}.score-row span{padding:3px 6px;border:1px solid #ead9a8;background:#fff;font-size:10px}.trace-stats{margin-top:10px;color:var(--ink-muted);font-size:11px}
@media(max-width:900px){.conversation-shell{grid-template-columns:210px minmax(0,1fr)}.message-stream{padding-right:20px;padding-left:20px}.composer{padding-right:20px;padding-left:20px}}
@media(max-width:700px){.assistant-header{min-height:66px;padding:10px 14px}.assistant-header p{display:none}.conversation-shell{display:block;min-height:0}.session-list{display:flex;overflow-x:auto;height:72px;padding:8px;border-right:0;border-bottom:1px solid var(--border);gap:8px}.session-list .section-heading,.session-list .new-chat,.session-list .el-empty{display:none}.session-list .task-item{flex:0 0 190px;margin:0;padding:8px}.session-list .task-item span,.session-list .task-item small{display:none}.message-stream{padding:18px 14px 28px}.composer{padding:8px 12px 10px}.composer .examples{display:none}.command-input{grid-template-columns:minmax(0,1fr) auto}.command-input .el-button{padding:8px 12px}.approval-gate{align-items:flex-start;flex-direction:column}.approval-gate .el-button{width:100%}.assistant-avatar{flex-basis:30px;width:30px;height:30px}.task-error{margin-left:42px}.report-columns{grid-template-columns:1fr}.evidence-list>div{grid-template-columns:1fr}.evidence-list span{overflow-wrap:anywhere}.kpi-strip{grid-template-columns:1fr 1fr}.plan-steps>div{grid-template-columns:22px minmax(0,1fr)}.plan-steps small{grid-column:2}}
</style>
