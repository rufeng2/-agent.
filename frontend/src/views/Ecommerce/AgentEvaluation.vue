<template>
  <section class="page-surface">
    <div class="page-heading"><div><h1>电商 Agent 评测</h1><p>使用 40 条标准问题评估意图、工具、参数、证据和风险准确率。</p></div><div class="toolbar-row"><el-switch v-model="online" active-text="DeepSeek 在线评测"/><el-button type="primary" :loading="running" @click="run">运行评测</el-button></div></div>
    <el-alert title="在线评测需要 DeepSeek API Key；未配置时自动执行确定性评测。" type="info" :closable="false"/>
    <div v-if="latest" class="metric-grid"><article v-for="key in metricKeys" :key="key" class="metric-card"><span>{{ labels[key] }}</span><strong>{{ latest.metrics[key] }}</strong></article></div>
    <div class="panel table-panel"><h2>评测历史</h2><el-table :data="items"><el-table-column prop="created_at" label="时间"/><el-table-column prop="mode" label="模式"/><el-table-column label="意图准确率"><template #default="{row}">{{ row.metrics.intent_accuracy }}%</template></el-table-column><el-table-column label="工具准确率"><template #default="{row}">{{ row.metrics.tool_accuracy }}%</template></el-table-column><el-table-column label="失败样例"><template #default="{row}">{{ row.metrics.failures?.length || 0 }}</template></el-table-column></el-table></div>
  </section>
</template>
<script setup lang="ts">
import { computed,onMounted,ref } from "vue"; import { ElMessage } from "element-plus"; import { ecommerceAPI } from "@/api/client"
const online=ref(false),running=ref(false),items=ref<any[]>([]);const latest=computed(()=>items.value[0]);const metricKeys=["intent_accuracy","tool_accuracy","parameter_accuracy","evidence_accuracy","risk_accuracy","p95_latency_ms"];const labels:any={intent_accuracy:"意图准确率/%",tool_accuracy:"工具准确率/%",parameter_accuracy:"参数准确率/%",evidence_accuracy:"证据准确率/%",risk_accuracy:"风险准确率/%",p95_latency_ms:"P95 耗时/ms"}
async function load(){items.value=(await ecommerceAPI.evaluations()).data.data} async function run(){running.value=true;try{await ecommerceAPI.runEvaluation(online.value);await load();ElMessage.success("评测完成")}catch{ElMessage.error("评测失败")}finally{running.value=false}} onMounted(load)
</script>
<style scoped>.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}.metric-card,.table-panel{padding:14px}.metric-card{background:#fff;border:1px solid var(--border);border-radius:6px}.metric-card span{display:block;color:var(--ink-muted);font-size:12px}.metric-card strong{display:block;margin-top:8px;font-size:21px}.table-panel{margin-top:16px}.table-panel h2{margin:0 0 12px;font-size:16px}</style>
