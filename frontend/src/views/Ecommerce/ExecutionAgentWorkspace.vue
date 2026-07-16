<template>
  <section class="page-surface execution-page">
    <div class="page-heading">
      <div><h1>执行型运营 Agent</h1><p>用自然语言下达业务任务，多 Agent 校验后在审批断点继续执行。</p></div>
      <div class="runtime-tags"><el-tag :type="mcpStatus==='ready'?'success':mcpStatus==='unavailable'?'danger':'info'" effect="plain">MCP {{ mcpStatus }}</el-tag><el-tag type="warning" effect="plain">Sandbox</el-tag></div>
    </div>

    <div class="command-band">
      <div class="command-input">
        <el-input v-model="goal" size="large" placeholder="例如：把轻量跑步鞋价格调整到 269 元" @keyup.enter="createTask" />
        <el-button type="primary" size="large" :loading="creating" @click="createTask">创建并运行</el-button>
      </div>
      <div class="examples">
        <button v-for="item in examples" :key="item" type="button" @click="goal=item">{{ item }}</button>
      </div>
    </div>

    <div class="workspace-grid">
      <aside class="task-list panel">
        <div class="section-heading"><h2>执行任务</h2><el-button text circle title="刷新" @click="loadTasks"><el-icon><Refresh /></el-icon></el-button></div>
        <el-empty v-if="!tasks.length" description="暂无执行任务" />
        <button v-for="item in tasks" :key="item.id" type="button" class="task-item" :class="{active:task?.id===item.id}" @click="task=item">
          <span>{{ statusLabel(item.status) }}</span><strong>{{ item.goal }}</strong><small>{{ actionLabel(item.state?.action_type) }} · v{{ item.version }}</small>
        </button>
      </aside>

      <main class="task-detail panel">
        <el-empty v-if="!task" description="输入执行命令开始任务" />
        <template v-else>
          <div class="task-title"><div><span>任务 {{ task.id.slice(0,8) }}</span><h2>{{ task.goal }}</h2></div><el-tag :type="statusType(task.status)">{{ statusLabel(task.status) }}</el-tag></div>

          <div v-if="task.state?.product" class="change-summary">
            <div><span>目标商品</span><strong>{{ task.state.product.name }}（{{ task.state.product.product_id }}）</strong></div>
            <div><span>执行动作</span><strong>{{ actionLabel(task.state.action_type) }}</strong></div>
            <div><span>风险等级</span><strong>{{ task.state.risk_level==='high'?'高风险':'中风险' }}</strong></div>
          </div>

          <h3>多 Agent 执行轨迹</h3>
          <div class="agent-timeline">
            <article v-for="(event,index) in task.events" :key="`${event.type}-${index}`">
              <span>{{ index+1 }}</span><div><strong>{{ event.agent }}</strong><p>{{ event.detail }}</p></div><small>{{ eventTypeLabel(event.type) }}</small>
            </article>
          </div>

          <section v-if="task.status==='waiting_approval'" class="approval-gate">
            <div><span>等待人工批准</span><h3>{{ task.state.approval_reason }}</h3><p>{{ parameterSummary(task.state) }}</p></div>
            <el-button type="primary" size="large" :loading="executing" @click="approve">批准并执行</el-button>
          </section>

          <section v-if="task.result?.status==='completed'" class="receipt">
            <div class="receipt-heading"><div><span>执行回执</span><h3>业务工具已完成写入</h3></div><el-tag type="success">{{ task.result.environment }}</el-tag></div>
            <div v-if="task.result.action_type!=='marketing_plan'" class="before-after">
              <div><span>执行前</span><strong>{{ snapshot(task.result.before,task.result.action_type) }}</strong></div>
              <div><span>执行后</span><strong>{{ snapshot(task.result.after,task.result.action_type) }}</strong></div>
            </div>
            <div v-else class="campaign-result"><span>已创建推广活动</span><strong>{{ task.result.campaign.name }}</strong><p>日预算 ¥{{ task.result.campaign.daily_budget }} · 目标 ACOS {{ task.result.campaign.target_acos_pct }}%</p></div>
            <div v-if="task.result.mcp" class="mcp-receipt"><span>MCP 工具调用</span><strong>{{ task.result.mcp.server }} · {{ task.result.mcp.tool || task.result.mcp.tools?.join(' + ') }}</strong><small>{{ task.result.mcp.transport }}</small></div>
            <div v-if="task.result.steps" class="dag-steps"><strong v-for="step in task.result.steps" :key="step.id">{{ step.id }} · {{ step.status }}</strong></div>
            <el-button v-if="task.status==='completed' && ['price_update','product_publish','product_unpublish'].includes(task.result.action_type)" :loading="executing" @click="rollback">回滚本次变更</el-button>
          </section>

          <el-alert v-if="task.error" type="error" :title="task.error" show-icon :closable="false" />
        </template>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Refresh } from "@element-plus/icons-vue"
import { ecommerceAPI } from "@/api/client"

const examples=["把轻量跑步鞋价格调整到 269 元","下架商品 P003","上架商品 P004","给轻量跑步鞋创建新品冷启动推广活动"]
const goal=ref(examples[0]),tasks=ref<any[]>([]),task=ref<any>(null),creating=ref(false),executing=ref(false)
const mcpStatus=ref("checking")
const message=(error:any)=>error?.response?.data?.detail||error?.message||"请求失败"
const statusLabel=(value:string)=>({planning:"规划中",waiting_approval:"待审批",running:"执行中",completed:"已完成",failed:"失败",rolled_back:"已回滚"} as any)[value]||value
const statusType=(value:string)=>value==="completed"?"success":value==="failed"?"danger":value==="waiting_approval"?"warning":"info"
const actionLabel=(value:string)=>({price_update:"调整价格",product_publish:"商品上架",product_unpublish:"商品下架",marketing_plan:"创建营销活动",composite:"复合执行任务"} as any)[value]||"待识别"
const eventTypeLabel=(value:string)=>({task_planned:"任务规划",dag_planned:"DAG 规划",context_loaded:"读取数据",mcp_tool_called:"MCP 读取",policy_validated:"策略校验",change_prepared:"准备变更",campaign_prepared:"生成活动",approval_required:"审批断点",approved:"恢复执行",task_completed:"工具回执",dag_completed:"DAG 完成",mcp_tool_completed:"MCP 回执",task_rolled_back:"回滚完成",mcp_rollback_completed:"MCP 回滚"} as any)[value]||value
function parameterSummary(state:any){if(["price_update","composite"].includes(state.action_type)){const price=`价格从 ¥${state.parameters.old_price} 调整到 ¥${state.parameters.new_price}，幅度 ${state.parameters.change_pct}%`;return state.action_type==="composite"?`${price}；随后创建“${state.parameters.campaign.name}”推广活动`:price}if(state.action_type==="marketing_plan")return `创建“${state.parameters.campaign.name}”，日预算 ¥${state.parameters.campaign.daily_budget}`;return `商品状态将改为 ${state.parameters.listing_status}`}
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
</style>
