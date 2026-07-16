<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>商品分析</h1>
        <p>查看商品分层、ABC 分层、GMV 贡献、转化效率、毛利、库存周转和评价风险。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="load">刷新商品</el-button>
    </div>

    <div class="panel table-panel">
      <el-table :data="products" stripe>
        <el-table-column prop="name" label="商品" min-width="150" />
        <el-table-column prop="category" label="类目" width="110" />
        <el-table-column prop="segment" label="商品分层" width="110">
          <template #default="{ row }"><el-tag>{{ row.segment }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="abc_segment" label="ABC 分层" width="100">
          <template #default="{ row }"><el-tag type="success">{{ row.abc_segment }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="gmv" label="GMV" width="110" />
        <el-table-column prop="orders" label="订单" width="90" />
        <el-table-column prop="conversion_rate" label="转化率" width="110" />
        <el-table-column prop="gross_margin_rate" label="毛利率" width="110" />
        <el-table-column label="库存" width="110">
          <template #default="{ row }">{{ row.stock }}/{{ row.safety_stock }}</template>
        </el-table-column>
        <el-table-column prop="inventory_turnover_days" label="周转天数" width="110" />
        <el-table-column prop="ad_roi" label="广告 ROI" width="110" />
        <el-table-column prop="average_rating" label="评分" width="90" />
        <el-table-column prop="competitor_price" label="竞品价" width="100" />
        <el-table-column prop="price_gap" label="价差" width="90" />
        <el-table-column prop="price_index" label="价格指数" width="100" />
        <el-table-column label="风险标签" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="tag in row.risk_tags" :key="tag" type="danger" style="margin-right:6px">{{ tag }}</el-tag>
            <span v-if="!row.risk_tags.length" class="muted">稳定</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"

const loading = ref(false)
const products = ref<any[]>([])

async function load() {
  loading.value = true
  try {
    products.value = (await ecommerceAPI.products()).data.data
  } catch {
    ElMessage.error("商品分析加载失败")
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.table-panel{padding:10px}.muted{color:var(--ink-muted);font-size:12px}
</style>
