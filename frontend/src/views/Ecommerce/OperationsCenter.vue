<template>
  <section class="page-surface">
    <div class="page-heading">
      <div><h1>运营任务中心</h1><p>{{ center?.date }} · 从经营数据生成今日任务、责任人和验收标准。</p></div>
      <el-button type="primary" :loading="loading" @click="load">刷新任务</el-button>
    </div>

    <div class="summary-strip">
      <article><span>今日任务</span><strong>{{ center?.tasks.length || 0 }}</strong><small>覆盖 7 个工作域</small></article>
      <article><span>紧急任务</span><strong class="danger">{{ urgentCount }}</strong><small>P0 优先处理</small></article>
      <article><span>低库存 SKU</span><strong>{{ center?.supply_chain.low_stock_skus || 0 }}</strong><small>供应链待确认</small></article>
      <article><span>退款率</span><strong>{{ center?.customer_service.refund_rate || 0 }}%</strong><small>客服与商品联动</small></article>
      <article><span>应急状态</span><strong :class="center?.incident.status">{{ incidentLabel }}</strong><small>{{ center?.incident.active_anomalies || 0 }} 项异常</small></article>
    </div>

    <div class="domain-tabs">
      <button :class="{active:domain==='all'}" @click="domain='all'">全部 <b>{{ center?.tasks.length || 0 }}</b></button>
      <button v-for="item in center?.domains || []" :key="item.id" :class="{active:domain===item.id}" @click="domain=item.id">{{ item.name }} <b>{{ taskCount(item.id) }}</b></button>
    </div>

    <div class="operations-layout">
      <div class="panel task-panel">
        <div class="panel-heading"><div><h2>{{ activeDomainName }}</h2><p>{{ activeDomainScope }}</p></div><el-tag effect="plain">{{ filteredTasks.length }} 项</el-tag></div>
        <el-table :data="filteredTasks" row-key="id">
          <el-table-column type="expand">
            <template #default="props">
              <div class="task-detail"><div><strong>数据依据</strong><ul><li v-for="item in props.row.evidence" :key="item">{{ item }}</li></ul></div><div><strong>验收指标</strong><p>{{ props.row.acceptance_metric }}</p></div></div>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="86"><template #default="scope"><el-tag :type="priorityType(scope.row.priority)">{{ scope.row.priority }}</el-tag></template></el-table-column>
          <el-table-column prop="title" label="今日任务" min-width="260" />
          <el-table-column prop="owner" label="负责人" width="110" />
          <el-table-column prop="deadline" label="截止时间" width="115" />
          <el-table-column label="状态" width="95"><template #default><el-tag type="info" effect="plain">待处理</el-tag></template></el-table-column>
        </el-table>
      </div>

      <aside class="side-column">
        <section class="panel side-panel"><h2>团队负载</h2><div v-for="item in center?.team_workload || []" :key="item.owner" class="workload-row"><div><strong>{{ item.owner }}</strong><small>{{ item.tasks }} 项任务</small></div><el-tag v-if="item.urgent" type="danger">{{ item.urgent }} 项紧急</el-tag><el-tag v-else type="success" effect="plain">正常</el-tag></div></section>
        <section class="panel side-panel"><h2>岗位工作域</h2><div v-for="item in center?.domains || []" :key="item.id" class="domain-row"><strong>{{ item.name }}</strong><p>{{ item.scope }}</p></div></section>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"
const loading=ref(false),center=ref<any>(null),domain=ref("all")
const urgentCount=computed(()=>center.value?.tasks.filter((item:any)=>item.priority==="P0").length||0)
const filteredTasks=computed(()=>domain.value==="all"?center.value?.tasks||[]:center.value?.tasks.filter((item:any)=>item.domain===domain.value)||[])
const activeDomain=computed(()=>center.value?.domains.find((item:any)=>item.id===domain.value))
const activeDomainName=computed(()=>activeDomain.value?.name||"全部运营任务")
const activeDomainScope=computed(()=>activeDomain.value?.scope||"按优先级处理今日经营、协同和风险事项")
const incidentLabel=computed(()=>({normal:"正常",attention:"关注",critical:"紧急"} as any)[center.value?.incident.status]||"--")
const taskCount=(id:string)=>center.value?.tasks.filter((item:any)=>item.domain===id).length||0
const priorityType=(value:string)=>value==="P0"?"danger":value==="P1"?"warning":"info"
async function load(){loading.value=true;try{center.value=(await ecommerceAPI.operationsCenter()).data.data}catch{ElMessage.error("运营任务加载失败")}finally{loading.value=false}}
onMounted(load)
</script>

<style scoped>
.summary-strip{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--border);background:#fff}.summary-strip article{padding:15px;border-right:1px solid var(--border)}.summary-strip article:last-child{border-right:0}.summary-strip span,.summary-strip strong,.summary-strip small{display:block}.summary-strip span,.summary-strip small{color:var(--ink-muted);font-size:12px}.summary-strip strong{margin:6px 0;font-size:22px}.summary-strip .danger,.summary-strip .critical{color:var(--danger)}.summary-strip .attention{color:#b45309}.summary-strip .normal{color:var(--success)}.domain-tabs{display:flex;gap:4px;margin:16px 0;overflow-x:auto}.domain-tabs button{flex:none;padding:8px 11px;border:1px solid var(--border);background:#fff;color:var(--ink);cursor:pointer}.domain-tabs button.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}.domain-tabs b{margin-left:5px;font-size:11px}.operations-layout{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px}.task-panel,.side-panel{padding:16px}.panel-heading{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}.panel-heading h2,.side-panel h2{margin:0;font-size:16px}.panel-heading p{margin:4px 0 0;color:var(--ink-muted)}.task-detail{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:4px 28px}.task-detail strong{font-size:13px}.task-detail ul,.task-detail p{margin:8px 0 0;color:var(--ink-muted);line-height:1.6}.side-column{display:grid;align-content:start;gap:16px}.workload-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 0;border-bottom:1px solid var(--border)}.workload-row strong,.workload-row small{display:block}.workload-row small{margin-top:3px;color:var(--ink-muted)}.domain-row{padding:10px 0;border-bottom:1px solid var(--border)}.domain-row p{margin:4px 0 0;color:var(--ink-muted);font-size:12px;line-height:1.5}
@media(max-width:1000px){.summary-strip{grid-template-columns:repeat(2,1fr)}.summary-strip article{border-bottom:1px solid var(--border)}.operations-layout{grid-template-columns:1fr}.side-column{grid-template-columns:1fr 1fr}}@media(max-width:620px){.summary-strip{grid-template-columns:1fr}.operations-layout,.side-column,.task-detail{grid-template-columns:1fr}.task-panel{overflow-x:auto}}
</style>
