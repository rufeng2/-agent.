import { createApp } from "vue"
import { createPinia } from "pinia"
import { ElAlert } from "element-plus/es/components/alert/index"
import { ElButton } from "element-plus/es/components/button/index"
import { ElCol } from "element-plus/es/components/col/index"
import { ElDropdown, ElDropdownItem, ElDropdownMenu } from "element-plus/es/components/dropdown/index"
import { ElEmpty } from "element-plus/es/components/empty/index"
import { ElForm, ElFormItem } from "element-plus/es/components/form/index"
import { ElIcon } from "element-plus/es/components/icon/index"
import { ElInput } from "element-plus/es/components/input/index"
import { ElRow } from "element-plus/es/components/row/index"
import { ElTabPane, ElTabs } from "element-plus/es/components/tabs/index"
import { ElTable, ElTableColumn } from "element-plus/es/components/table/index"
import { ElTag } from "element-plus/es/components/tag/index"
import "element-plus/dist/index.css"

import App from "./App.vue"
import router from "./router"
import "./styles/global.css"

const app = createApp(App)

app.component("ElAlert", ElAlert)
app.component("ElButton", ElButton)
app.component("ElCol", ElCol)
app.component("ElDropdown", ElDropdown)
app.component("ElDropdownItem", ElDropdownItem)
app.component("ElDropdownMenu", ElDropdownMenu)
app.component("ElEmpty", ElEmpty)
app.component("ElForm", ElForm)
app.component("ElFormItem", ElFormItem)
app.component("ElIcon", ElIcon)
app.component("ElInput", ElInput)
app.component("ElRow", ElRow)
app.component("ElTabPane", ElTabPane)
app.component("ElTable", ElTable)
app.component("ElTableColumn", ElTableColumn)
app.component("ElTabs", ElTabs)
app.component("ElTag", ElTag)

app.use(createPinia())
app.use(router)

app.mount("#app")
