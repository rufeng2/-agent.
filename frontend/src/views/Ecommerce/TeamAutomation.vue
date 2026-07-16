<template>
  <section class="page-surface">
    <div class="page-heading"><div><h1>团队与自动化</h1><p>管理专员业务记忆，以及让团队主动巡检和处理事件。</p></div><el-tag type="success" effect="plain">5 Agents</el-tag></div>
    <el-tabs v-model="tab" class="team-tabs">
      <el-tab-pane label="主动自动化" name="automation">
        <div class="automation-summary"><article><span>自动化规则</span><strong>{{ rules.length }}</strong></article><article><span>运行中</span><strong>{{ rules.filter(x=>x.enabled).length }}</strong></article><article><span>累计触发</span><strong>{{ rules.reduce((n,x)=>n+x.run_count,0) }}</strong></article></div>
        <div class="rule-list">
          <article v-for="rule in rules" :key="rule.id" class="panel rule-card">
            <div class="rule-head"><div><el-tag effect="plain">{{ triggerLabel(rule.trigger_type) }}</el-tag><h2>{{ rule.name }}</h2></div><el-switch v-model="rule.enabled" @change="toggle(rule)" /></div>
            <p>{{ rule.task_prompt }}</p>
            <div class="rule-meta"><span>每 {{ intervalLabel(rule.interval_minutes) }}</span><span>已运行 {{ rule.run_count }} 次</span><span>{{ rule.last_run_at ? formatTime(rule.last_run_at) : '尚未运行' }}</span></div>
            <el-button :disabled="!rule.enabled" :loading="runningId===rule.id" @click="run(rule)">立即运行</el-button>
          </article>
        </div>
        <div class="panel webhook-panel"><h2>Webhook 事件入口</h2><p>外部订单、退货、库存和差评事件会创建主管任务，沿用专员协作、记忆和审计链路。</p><div><el-tag>order_created</el-tag><el-tag>return_created</el-tag><el-tag>inventory_changed</el-tag><el-tag>negative_review</el-tag></div></div>
      </el-tab-pane>
      <el-tab-pane label="专员记忆" name="memory">
        <div class="memory-grid">
          <article v-for="item in memories" :key="`${item.agent}-${item.key}`" class="panel memory-card">
            <div class="memory-head"><div><span>{{ agentLabel(item.agent) }}</span><h2>{{ keyLabel(item.key) }}</h2></div><el-tag :type="item.source==='user'?'success':'info'" effect="plain">{{ item.source==='user'?'人工规则':'系统默认' }}</el-tag></div>
            <el-input v-model="item.editor" type="textarea" :rows="7" />
            <div class="memory-footer"><small>{{ formatTime(item.updated_at) }}</small><el-button type="primary" @click="saveMemory(item)">保存记忆</el-button></div>
          </article>
        </div>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"
const tab=ref("automation"),rules=ref<any[]>([]),memories=ref<any[]>([]),runningId=ref("")
const agentNames:any={product_research:"选品专员",pricing:"定价专员",listing:"Listing 专员",advertising:"推广专员",customer_service:"客服专员"}
const keys:any={selection_policy:"选品规则",pricing_policy:"定价底线",brand_policy:"品牌与合规规则",advertising_policy:"广告目标",service_policy:"客服规则",last_deliverable:"最近一次交付物"}
const agentLabel=(v:string)=>agentNames[v]||v,keyLabel=(v:string)=>keys[v]||v,triggerLabel=(v:string)=>v==="cron"?"定时任务":"心跳巡检"
const intervalLabel=(v:number)=>v>=1440?`${v/1440} 天`:v>=60?`${v/60} 小时`:`${v} 分钟`
const formatTime=(v:string)=>v?new Date(v).toLocaleString():"--"
async function load(){const [a,m]=await Promise.all([ecommerceAPI.automations(),ecommerceAPI.teamMemories()]);rules.value=a.data.data;memories.value=m.data.data.map((x:any)=>({...x,editor:JSON.stringify(x.value,null,2)}))}
async function toggle(rule:any){await ecommerceAPI.toggleAutomation(rule.id,rule.enabled);ElMessage.success(rule.enabled?"自动化已启用":"自动化已暂停")}
async function run(rule:any){runningId.value=rule.id;try{const d=(await ecommerceAPI.runAutomation(rule.id)).data.data;rule.run_count+=1;rule.last_run_at=new Date().toISOString();ElMessage.success(`已创建主管任务 ${d.job_id.slice(0,8)}`)}finally{runningId.value=""}}
async function saveMemory(item:any){try{const value=JSON.parse(item.editor);await ecommerceAPI.updateTeamMemory(item.agent,item.key,value);item.source="user";ElMessage.success(`${agentLabel(item.agent)}记忆已更新`)}catch{ElMessage.error("记忆必须是合法 JSON")}}
onMounted(load)
</script>

<style scoped>
.team-tabs{padding:0 18px 18px;border:1px solid var(--border);background:#fff}.automation-summary{display:grid;grid-template-columns:repeat(3,1fr);margin:4px 0 16px;border:1px solid var(--border)}.automation-summary article{padding:14px;border-right:1px solid var(--border)}.automation-summary article:last-child{border-right:0}.automation-summary span,.automation-summary strong{display:block}.automation-summary span{color:var(--ink-muted);font-size:12px}.automation-summary strong{margin-top:5px;font-size:22px}.rule-list{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.rule-card,.memory-card,.webhook-panel{padding:16px}.rule-head,.memory-head,.memory-footer{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.rule-head>div{display:flex;align-items:center;gap:9px}.rule-head h2,.memory-head h2,.webhook-panel h2{margin:0;font-size:16px}.rule-card>p,.webhook-panel p{color:var(--ink-muted);line-height:1.6}.rule-meta{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0;color:var(--ink-muted);font-size:12px}.webhook-panel{margin-top:14px}.webhook-panel .el-tag{margin-right:8px}.memory-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.memory-head{margin-bottom:12px}.memory-head span{color:var(--ink-muted);font-size:12px}.memory-head h2{margin-top:3px}.memory-footer{align-items:center;margin-top:10px}.memory-footer small{color:var(--ink-muted)}@media(max-width:800px){.rule-list,.memory-grid{grid-template-columns:1fr}}@media(max-width:520px){.automation-summary{grid-template-columns:1fr}.automation-summary article{border-right:0;border-bottom:1px solid var(--border)}}
</style>
