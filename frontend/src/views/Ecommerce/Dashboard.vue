<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>运营驾驶舱</h1>
        <p>实时查看 GMV、转化、广告 ROI、库存和评价异常。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="load">刷新数据</el-button>
    </div>

    <div class="metric-grid">
      <article v-for="(item, key) in dashboard?.kpis" :key="key" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}{{ item.unit }}</strong>
        <em :class="item.trend">环比 {{ item.delta_pct }}%</em>
      </article>
    </div>

    <el-row :gutter="16" class="section-row">
      <el-col :xs="24" :lg="14">
        <div class="panel section-panel">
          <h2>GMV 趋势图</h2>
          <div class="trend-chart">
            <div v-for="row in dashboard?.trend || []" :key="row.date" class="trend-bar">
              <span>{{ row.date.slice(5) }}</span>
              <div><i :style="{ height: trendHeight(row.gmv) + '%' }"></i></div>
              <b>{{ row.gmv }}</b>
            </div>
          </div>
          <el-table :data="dashboard?.trend || []">
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="gmv" label="GMV" />
            <el-table-column prop="orders" label="订单数" />
          </el-table>
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="panel section-panel">
          <h2>异常提醒</h2>
          <el-empty v-if="!dashboard?.anomalies?.length" description="暂无异常" />
          <div v-for="item in dashboard?.anomalies || []" :key="item.id" class="alert-item">
            <el-tag :type="item.severity === 'high' ? 'danger' : 'warning'">{{ item.severity }}</el-tag>
            <strong>{{ item.title }}</strong>
            <p>{{ item.summary }}</p>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="panel section-panel attribution-panel">
      <h2>GMV 归因</h2>
      <div class="attribution-grid">
        <article v-for="item in dashboard?.gmv_attribution || []" :key="item.factor" class="attribution-item">
          <div>
            <strong>{{ item.label }}</strong>
            <span>{{ item.insight }}</span>
          </div>
          <b :class="{ negative: item.delta_value < 0, positive: item.delta_value > 0 }">{{ item.delta_value }} 元</b>
          <div class="impact-track"><i :class="{ negative: item.delta_value < 0, positive: item.delta_value > 0 }" :style="{ width: impactWidth(item.contribution_pct) + '%' }"></i></div>
          <small>贡献度 {{ item.contribution_pct }}%</small>
        </article>
      </div>
    </div>
    <el-row :gutter="16" class="section-row">
      <el-col :xs="24" :lg="12"><div class="panel section-panel"><h2>转化漏斗</h2><div v-for="stage in funnel?.stages || []" :key="stage.name" class="funnel-row"><span>{{ stage.name }}</span><b>{{ stage.value }}</b><small>{{ stage.conversion_from_previous }}%</small></div></div></el-col>
      <el-col :xs="24" :lg="12"><div class="panel section-panel"><h2>未来 7 天 GMV 模拟预测</h2><el-table :data="forecast?.points || []"><el-table-column prop="date" label="日期"/><el-table-column prop="predicted_gmv" label="预测 GMV"/><el-table-column prop="lower" label="下界"/><el-table-column prop="upper" label="上界"/></el-table></div></el-col>
    </el-row>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus/es/components/message/index"
import { ecommerceAPI } from "@/api/client"

const loading = ref(false)
const dashboard = ref<any>(null)
const funnel = ref<any>(null), forecast=ref<any>(null)
const maxGmv = computed(() => Math.max(...(dashboard.value?.trend || []).map((row: any) => Number(row.gmv)), 1))

function trendHeight(value: number) {
  return Math.max(12, Math.round(Number(value) / maxGmv.value * 100))
}

function impactWidth(value: number) {
  return Math.min(100, Math.max(8, Math.abs(Number(value))))
}

async function load() {
  loading.value = true
  try {
    const [a,b,c]=await Promise.all([ecommerceAPI.dashboard(),ecommerceAPI.funnel(),ecommerceAPI.forecast()]);dashboard.value=a.data.data;funnel.value=b.data.data;forecast.value=c.data.data
  } catch {
    ElMessage.error("运营数据加载失败")
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.metric-card{background:#fff;border:1px solid var(--border);border-radius:6px;padding:16px}.metric-card span{display:block;color:var(--ink-muted);font-size:12px}.metric-card strong{display:block;margin-top:8px;font-size:24px}.metric-card em{font-style:normal;font-size:12px}.metric-card em.down,.negative{color:var(--danger)}.metric-card em.up,.positive{color:var(--success)}.section-row{margin-top:16px}.section-panel{padding:16px}.section-panel h2{margin:0 0 12px;font-size:16px}.trend-chart{display:flex;align-items:end;gap:12px;height:170px;margin-bottom:14px;padding:12px;border:1px solid var(--border);border-radius:6px;background:#f8fafc;overflow-x:auto}.trend-bar{display:grid;grid-template-rows:1fr auto auto;gap:6px;align-items:end;min-width:62px;text-align:center}.trend-bar div{display:flex;align-items:end;justify-content:center;height:104px}.trend-bar i{display:block;width:28px;border-radius:4px 4px 0 0;background:#2563eb}.trend-bar span,.trend-bar b{font-size:12px;color:var(--ink-muted)}.alert-item{border-top:1px solid var(--border);padding:12px 0}.alert-item:first-of-type{border-top:0}.alert-item strong{display:block;margin:6px 0}.alert-item p{margin:0;color:var(--ink-muted);line-height:1.6}.attribution-panel{margin-top:16px}.attribution-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.attribution-item{border:1px solid var(--border);border-radius:6px;padding:14px;background:#fff}.attribution-item strong,.attribution-item b,.attribution-item span,.attribution-item small{display:block}.attribution-item span{margin-top:4px;color:var(--ink-muted);font-size:12px;line-height:1.5}.attribution-item b{margin-top:12px;font-size:20px}.impact-track{height:6px;margin:8px 0;background:#eef2f6;border-radius:999px;overflow:hidden}.impact-track i{display:block;height:100%;background:var(--success)}.impact-track i.negative{background:var(--danger)}.attribution-item small{margin-top:4px;color:var(--ink-muted)}.funnel-row{display:grid;grid-template-columns:1fr auto 70px;gap:12px;padding:9px;border-bottom:1px solid var(--border)}.funnel-row small{text-align:right;color:var(--ink-muted)}
</style>
