<template>
  <section class="page-surface">
    <div class="page-heading"><div><h1>客户分析</h1><p>基于 RFM、复购率和模拟 LTV 识别客户价值与流失风险。</p></div><el-button type="primary" :loading="loading" @click="load">刷新分析</el-button></div>
    <div class="metric-grid">
      <article class="metric-card"><span>客户数</span><strong>{{ data?.customers?.length || 0 }}</strong></article>
      <article class="metric-card"><span>复购率</span><strong>{{ data?.repeat_purchase_rate || 0 }}%</strong></article>
      <article class="metric-card"><span>平均模拟 LTV</span><strong>{{ data?.average_ltv || 0 }} 元</strong></article>
    </div>
    <div class="panel content-panel">
      <h2>RFM 分层</h2>
      <div class="segment-row"><el-tag v-for="(count, name) in data?.segment_counts || {}" :key="name">{{ name }} {{ count }}</el-tag></div>
      <el-table :data="data?.customers || []" stripe height="520">
        <el-table-column prop="customer_id" label="客户" />
        <el-table-column prop="recency_days" label="最近消费/天" />
        <el-table-column prop="frequency" label="消费频次" />
        <el-table-column prop="monetary" label="累计 GMV" />
        <el-table-column prop="segment" label="客户分层"><template #default="{ row }"><el-tag :type="row.segment === '流失风险' ? 'danger' : 'success'">{{ row.segment }}</el-tag></template></el-table-column>
      </el-table>
    </div>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"
const loading = ref(false); const data = ref<any>(null)
async function load(){ loading.value=true; try{data.value=(await ecommerceAPI.customers()).data.data}catch{ElMessage.error("客户分析加载失败")}finally{loading.value=false} }
onMounted(load)
</script>
<style scoped>
.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric-card,.content-panel{padding:16px}.metric-card{background:#fff;border:1px solid var(--border);border-radius:6px}.metric-card span{display:block;color:var(--ink-muted)}.metric-card strong{display:block;margin-top:8px;font-size:22px}.content-panel{margin-top:16px}.content-panel h2{margin:0 0 12px;font-size:16px}.segment-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}@media(max-width:760px){.metric-grid{grid-template-columns:1fr}}
</style>
