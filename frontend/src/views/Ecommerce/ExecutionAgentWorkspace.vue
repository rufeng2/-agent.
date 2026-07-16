<template>
  <section class="assistant-page">
    <header class="assistant-header">
      <div><h1>电商运营执行助手</h1><p>对话下达任务，确认后由多 Agent 调用业务工具执行。</p></div>
      <div class="runtime-tags"><el-tag :type="mcpStatus==='ready'?'success':mcpStatus==='unavailable'?'danger':'info'" effect="plain">MCP {{ mcpStatus }}</el-tag><el-tag type="warning" effect="plain">沙箱</el-tag></div>
    </header>
    <div class="conversation-shell">
      <aside class="session-list">
        <div class="section-heading"><h2>会话</h2><el-button text circle title="刷新" @click="loadTasks"><el-icon><Refresh /></el-icon></el-button></div>
        <el-button class="new-chat" @click="task=null;goal=''">新建会话</el-button>
        <el-empty v-if="!tasks.length" description="暂无执行任务" />
        <button v-for="item in tasks" :key="item.id" type="button" class="task-item" :class="{active:task?.id===item.id}" @click="task=item">
          <span>{{ statusLabel(item.status) }}</span><strong>{{ item.goal }}</strong><small>{{ actionLabel(item.state?.action_type) }} · v{{ item.version }}</small>
        </button>
      </aside>
      <main class="conversation-main">
        <div class="message-stream">
        <div v-if="!task" class="welcome-message">
          <div class="assistant-avatar">AI</div><div><h2>需要我执行什么运营任务？</h2><p>可以生成推广文案、调整商品价格、上下架商品或创建营销活动。</p></div>
        </div>
        <template v-else>
          <div class="message user-message"><div class="message-body"><small>你</small><p>{{ task.goal }}</p></div></div>
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
          <small>业务写操作会在执行前请求你的确认</small>
        </footer>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Refresh } from "@element-plus/icons-vue"
import { ecommerceAPI } from "@/api/client"

const examples=["给便携榨汁杯做一个小红书推广文案","把轻量跑步鞋价格调整到 269 元","下架商品 P003","给轻量跑步鞋创建新品冷启动推广活动"]
const goal=ref(examples[0]),tasks=ref<any[]>([]),task=ref<any>(null),creating=ref(false),executing=ref(false)
const mcpStatus=ref("checking")
const message=(error:any)=>error?.response?.data?.detail||error?.message||"请求失败"
const statusLabel=(value:string)=>({planning:"规划中",waiting_approval:"待审批",running:"执行中",completed:"已完成",failed:"失败",rolled_back:"已回滚"} as any)[value]||value
const statusType=(value:string)=>value==="completed"?"success":value==="failed"?"danger":value==="waiting_approval"?"warning":"info"
const actionLabel=(value:string)=>({price_update:"调整价格",product_publish:"商品上架",product_unpublish:"商品下架",marketing_plan:"创建营销活动",content_generation:"生成推广文案",composite:"复合执行任务"} as any)[value]||"待识别"
const eventTypeLabel=(value:string)=>({task_planned:"任务规划",dag_planned:"DAG 规划",context_loaded:"读取数据",mcp_tool_called:"MCP 读取",policy_validated:"策略校验",change_prepared:"准备变更",campaign_prepared:"生成活动",copy_generated:"生成文案",approval_required:"审批断点",approved:"恢复执行",task_completed:"工具回执",content_delivered:"文案交付",dag_completed:"DAG 完成",mcp_tool_completed:"MCP 回执",task_rolled_back:"回滚完成",mcp_rollback_completed:"MCP 回滚"} as any)[value]||value
function parameterSummary(state:any){if(["price_update","composite"].includes(state.action_type)){const price=`价格从 ¥${state.parameters.old_price} 调整到 ¥${state.parameters.new_price}，幅度 ${state.parameters.change_pct}%`;return state.action_type==="composite"?`${price}；随后创建“${state.parameters.campaign.name}”推广活动`:price}if(state.action_type==="marketing_plan")return `创建“${state.parameters.campaign.name}”，日预算 ¥${state.parameters.campaign.daily_budget}`;if(state.action_type==="content_generation")return `审核“${state.parameters.copy.headline}”及正文、卖点和 CTA，通过后交付`;return `商品状态将改为 ${state.parameters.listing_status}`}
function snapshot(value:any,type:string){return ["price_update","composite"].includes(type)?`¥${value.price} · 版本 ${value.catalog_version}`:`${value.listing_status==='listed'?'已上架':'已下架'} · 版本 ${value.catalog_version}`}
async function loadTasks(){tasks.value=(await ecommerceAPI.executionTasks()).data.data;if(task.value)task.value=tasks.value.find((item:any)=>item.id===task.value.id)||task.value}
async function loadMcpStatus(){try{mcpStatus.value=(await ecommerceAPI.mcpStatus()).data.data.status}catch{mcpStatus.value="unavailable"}}
async function createTask(){if(!goal.value.trim())return;creating.value=true;try{task.value=(await ecommerceAPI.createExecutionTask(goal.value)).data.data;await loadTasks();ElMessage.success("任务已运行到审批断点")}catch(error:any){ElMessage.error(message(error))}finally{creating.value=false}}
async function approve(){await ElMessageBox.confirm("批准后将立即修改模拟业务系统，是否继续？","执行确认",{type:"warning",confirmButtonText:"批准并执行"});executing.value=true;try{task.value=(await ecommerceAPI.approveExecutionTask(task.value.id,task.value.version,"已核对执行参数")).data.data;await loadTasks();ElMessage.success("任务执行完成")}catch(error:any){ElMessage.error(message(error))}finally{executing.value=false}}
async function rollback(){await ElMessageBox.confirm("将业务状态恢复到本任务执行前，是否继续？","回滚确认",{type:"warning"});executing.value=true;try{task.value=(await ecommerceAPI.rollbackExecutionTask(task.value.id,task.value.version)).data.data;await loadTasks();ElMessage.success("变更已回滚")}catch(error:any){ElMessage.error(message(error))}finally{executing.value=false}}
onMounted(()=>Promise.all([loadTasks(),loadMcpStatus()]))
</script>

<style scoped>
.command-band{padding:18px;margin-bottom:16px;border:1px solid var(--border);background:#fff}.command-input{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px}.examples{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.examples button{padding:8px 10px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--ink-muted);cursor:pointer}.examples button:hover{border-color:#2563eb;color:#1d4ed8}.workspace-grid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:16px}.task-list,.task-detail{padding:16px}.section-heading,.task-title,.receipt-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.section-heading h2,.task-title h2{margin:0}.section-heading h2{font-size:16px}.task-item{display:grid;width:100%;gap:5px;margin-top:8px;padding:11px;text-align:left;border:1px solid var(--border);border-radius:5px;background:#fff;cursor:pointer}.task-item.active{border-color:#2563eb;background:#f5f8ff}.task-item span,.task-item small,.task-title span,.change-summary span,.approval-gate span,.receipt span{color:var(--ink-muted);font-size:12px}.task-item strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-title h2{margin-top:5px;font-size:18px}.change-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.change-summary>div,.before-after>div{padding:12px;border:1px solid var(--border)}.change-summary strong,.change-summary span,.before-after strong,.before-after span{display:block}.change-summary strong,.before-after strong{margin-top:5px}.task-detail h3{font-size:15px}.agent-timeline{display:grid;gap:8px}.agent-timeline article{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:10px;align-items:center;padding:11px;border-bottom:1px solid var(--border)}.agent-timeline article>span{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#111827;color:#fff}.agent-timeline p{margin:4px 0 0;color:var(--ink-muted)}.agent-timeline small{color:#1d4ed8}.approval-gate{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:18px;padding:16px;border-left:4px solid #f59e0b;background:#fffbeb}.approval-gate h3{margin:5px 0}.approval-gate p{margin:0;color:var(--ink-muted)}.receipt{margin-top:18px;padding:16px;border-left:4px solid #16a34a;background:#f4faf6}.receipt h3{margin:5px 0}.before-after{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.campaign-result{margin:14px 0;padding:12px;border:1px solid #cce3d2;background:#fff}.campaign-result strong{display:block;margin-top:5px}.campaign-result p{margin-bottom:0;color:var(--ink-muted)}@media(max-width:900px){.workspace-grid{grid-template-columns:1fr}.task-list{max-height:260px;overflow:auto}.change-summary{grid-template-columns:1fr}}@media(max-width:600px){.command-input{grid-template-columns:1fr}.approval-gate{align-items:flex-start;flex-direction:column}.approval-gate .el-button{width:100%}.before-after{grid-template-columns:1fr}.agent-timeline article{grid-template-columns:28px minmax(0,1fr)}.agent-timeline small{grid-column:2}}
.mcp-receipt{display:flex;align-items:center;gap:10px;margin:12px 0;padding:10px;border:1px solid #cce3d2;background:#fff}.mcp-receipt span,.mcp-receipt small{color:var(--ink-muted);font-size:12px}.mcp-receipt small{margin-left:auto}@media(max-width:600px){.mcp-receipt{align-items:flex-start;flex-direction:column}.mcp-receipt small{margin-left:0}}
.dag-steps{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.dag-steps strong{padding:7px 9px;border:1px solid #cce3d2;background:#fff;color:#166534;font-size:12px}
.copy-result{margin:14px 0;padding:16px;border:1px solid #cce3d2;background:#fff}.copy-meta{display:flex;align-items:center;justify-content:space-between;gap:12px}.copy-result h4{margin:14px 0 8px;font-size:20px}.copy-result p{color:var(--ink-muted);line-height:1.8;white-space:pre-wrap}.copy-result ul{padding-left:20px;line-height:1.9}.copy-cta{display:inline-block;margin:8px 0;color:#166534}.copy-result small{display:block;color:var(--ink-muted);line-height:1.7}
.assistant-page{display:flex;flex-direction:column;height:100%;min-height:0;background:#fff}.assistant-header{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:76px;padding:14px 24px;border-bottom:1px solid var(--border)}.assistant-header h1{margin:0;font-size:20px}.assistant-header p{margin:4px 0 0;color:var(--ink-muted);font-size:12px}.runtime-tags{display:flex;gap:8px}.conversation-shell{display:grid;grid-template-columns:260px minmax(0,1fr);flex:1;min-height:0}.session-list{overflow:auto;padding:16px 12px;background:#f7f9f8;border-right:1px solid var(--border)}.new-chat{width:100%;margin:10px 0 4px}.conversation-main{display:flex;min-width:0;min-height:0;flex-direction:column;background:#fff}.message-stream{flex:1;overflow:auto;padding:28px max(28px,calc((100% - 840px)/2)) 40px}.welcome-message,.message{display:flex;gap:12px;margin-bottom:22px}.welcome-message{align-items:flex-start;padding-top:8vh}.welcome-message h2{margin:2px 0 6px;font-size:20px}.welcome-message p{margin:0;color:var(--ink-muted)}.assistant-avatar{display:grid;flex:0 0 34px;width:34px;height:34px;place-items:center;border-radius:50%;background:#17201c;color:#fff;font-size:11px;font-weight:700}.message-body{min-width:0;max-width:760px}.user-message{justify-content:flex-end}.user-message .message-body{padding:11px 15px;border-radius:8px 2px 8px 8px;background:#edf4ff}.user-message small{color:#47627f}.user-message p{margin:4px 0 0;line-height:1.65}.assistant-message .message-body{flex:1;padding:2px 0}.message-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.message-body>p{line-height:1.7;color:#495650}.plan-facts{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.plan-facts span{padding:5px 8px;border:1px solid var(--border);border-radius:4px;color:var(--ink-muted);font-size:12px}.agent-details{margin-top:12px;border-top:1px solid var(--border)}.agent-details summary{padding:11px 0;color:#2563eb;cursor:pointer;font-size:12px}.agent-timeline article{padding:10px 0}.approval-gate,.receipt{max-width:760px;margin:0;padding:16px;border:1px solid #ead9a8;border-left:4px solid #f59e0b;border-radius:5px;background:#fffbeb}.receipt{border-color:#cce3d2;border-left-color:#16a34a;background:#f4faf6}.approval-gate{display:flex;align-items:center;justify-content:space-between;gap:18px}.approval-gate h3{font-size:14px}.composer{padding:10px max(24px,calc((100% - 840px)/2)) 14px;background:#fff;border-top:1px solid var(--border);box-shadow:0 -8px 20px rgba(24,32,29,.04)}.composer .examples{margin:0 0 8px;overflow:hidden;flex-wrap:nowrap}.composer .examples button{flex:0 0 auto;padding:5px 8px;font-size:11px}.composer>small{display:block;margin-top:6px;color:var(--ink-muted);text-align:center;font-size:11px}.task-error{max-width:760px;margin-left:46px}.session-list .task-item{background:transparent}.session-list .task-item.active{background:#fff}
@media(max-width:900px){.conversation-shell{grid-template-columns:210px minmax(0,1fr)}.message-stream{padding-right:20px;padding-left:20px}.composer{padding-right:20px;padding-left:20px}}
@media(max-width:700px){.assistant-header{min-height:66px;padding:10px 14px}.assistant-header p{display:none}.conversation-shell{display:block;min-height:0}.session-list{display:flex;overflow-x:auto;height:72px;padding:8px;border-right:0;border-bottom:1px solid var(--border);gap:8px}.session-list .section-heading,.session-list .new-chat,.session-list .el-empty{display:none}.session-list .task-item{flex:0 0 190px;margin:0;padding:8px}.session-list .task-item span,.session-list .task-item small{display:none}.message-stream{padding:18px 14px 28px}.composer{padding:8px 12px 10px}.composer .examples{display:none}.command-input{grid-template-columns:minmax(0,1fr) auto}.command-input .el-button{padding:8px 12px}.approval-gate{align-items:flex-start;flex-direction:column}.approval-gate .el-button{width:100%}.assistant-avatar{flex-basis:30px;width:30px;height:30px}.task-error{margin-left:42px}}
</style>
