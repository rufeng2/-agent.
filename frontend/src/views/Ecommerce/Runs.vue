<template>
  <section class="page-surface">
    <div class="page-heading"><div><h1>Agent 运行中心</h1><p>查看执行模式、降级率、耗时、Token 和工具调用轨迹。</p></div><el-button type="primary" :loading="loading" @click="load">刷新</el-button></div>
    <div class="metric-grid"><article v-for="(value,key) in summary" :key="key" class="metric-card"><span>{{ labels[key] || key }}</span><strong>{{ value }}</strong></article></div>
    <div class="panel table-panel"><div class="filters"><el-select v-model="mode" clearable placeholder="执行模式" @change="load"><el-option label="LLM" value="llm"/><el-option label="确定性降级" value="deterministic_fallback"/></el-select></div>
      <el-table :data="runs" stripe @row-click="open"><el-table-column prop="created_at" label="时间" min-width="170"/><el-table-column prop="execution_mode" label="执行模式" min-width="160"/><el-table-column prop="status" label="状态"/><el-table-column prop="fallback_reason" label="降级原因" min-width="160"/><el-table-column prop="total_latency_ms" label="耗时/ms"/></el-table>
    </div>
    <el-drawer v-model="visible" title="工具执行轨迹" size="520px"><el-timeline><el-timeline-item v-for="tool in detail?.tools || []" :key="tool.tool_name" :timestamp="tool.tool_name"><strong>{{ tool.output_summary }}</strong><pre>{{ JSON.stringify(tool.input, null, 2) }}</pre></el-timeline-item></el-timeline></el-drawer>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue"; import { ecommerceAPI } from "@/api/client"
const loading=ref(false), mode=ref(""), runs=ref<any[]>([]), summary=ref<any>({}), detail=ref<any>(null), visible=ref(false)
const labels:any={total_runs:"运行次数",success_rate:"成功率/%",fallback_rate:"降级率/%",average_latency_ms:"平均耗时/ms",p95_latency_ms:"P95/ms",total_tokens:"Token"}
async function load(){loading.value=true;try{const [a,b]=await Promise.all([ecommerceAPI.runs(mode.value),ecommerceAPI.runSummary()]);runs.value=a.data.data;summary.value=b.data.data}finally{loading.value=false}}
async function open(row:any){detail.value=(await ecommerceAPI.runDetail(row.id)).data.data;visible.value=true} onMounted(load)
</script>
<style scoped>.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}.metric-card,.table-panel{padding:14px}.metric-card{background:#fff;border:1px solid var(--border);border-radius:6px}.metric-card span{display:block;color:var(--ink-muted);font-size:12px}.metric-card strong{display:block;margin-top:7px;font-size:20px}.table-panel{margin-top:16px}.filters{margin-bottom:12px}.filters .el-select{width:200px}pre{white-space:pre-wrap;word-break:break-word;background:#f5f7f6;padding:10px;border-radius:6px}</style>
