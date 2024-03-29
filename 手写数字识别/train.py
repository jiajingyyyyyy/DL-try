import torch
import torchvision
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
"""
# 设计一个卷积神经网络，并在其中使用ResNet模块，在MNIST数据集上实现10分类手写体数字识别。
# 算一下每个数字的准确率
# 超参数
epochs = 10
batch_size_train = 64
batch_size_test = 1000
learning_rate = 0.01
# 这里的log_interval是指每隔多少个batch输出一次训练状态
log_interval = batch_size_train
random_seed = 1
# 设置种子，为了使得结果可复现
torch.manual_seed(random_seed)

# 从torchvision.datasets中加载MNIST数据集，并对数据进行标准化处理,参考网上
train_loader = torch.utils.data.DataLoader(
    torchvision.datasets.MNIST('./data/', train=True, download=True,
                               transform=torchvision.transforms.Compose([
                                   torchvision.transforms.ToTensor(),
                                   # 这里设置均值和方差的值
                                   torchvision.transforms.Normalize(
                                       (0.1307,), (0.3081,))
                               ])),
    batch_size=batch_size_train, shuffle=True)
test_loader = torch.utils.data.DataLoader(
    torchvision.datasets.MNIST('./data/', train=False, download=True,
                               transform=torchvision.transforms.Compose([
                                   torchvision.transforms.ToTensor(),
                                   torchvision.transforms.Normalize(
                                       (0.1307,), (0.3081,))
                               ])),
    batch_size=batch_size_test, shuffle=True)


# 定义残差模块
class ResidualBlock(torch.nn.Module):
    # 这里stride是指卷积的步长,保持输入输出的维度不变
    def __init__(self, in_channels, out_channels, stride=1):
        super(ResidualBlock, self).__init__()
        # padding为1，保证输入输出的维度不变,bias=False,因为后面有BN层
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        # 这里的inplace=True是指将ReLU的输出直接覆盖到输入中，可以节省的显存，但是会影响收敛性
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.downsample = nn.Sequential()
        # 这里的downsample是指如果输入输出的维度不一致，就需要对输入进行下采样，使得维度一致
        # 原理是使用1*1的卷积核对输入进行卷积，同时步长为stride，这样就可以保证输入输出的维度一致
        if stride != 1 or in_channels != out_channels:
            self.downsample = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        # 保存输入数据，采用恒等映射
        identity = x

        # 第一个卷积层
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        # 第二个卷积层
        out = self.conv2(out)
        out = self.bn2(out)

        # 下采样匹配卷积操作的输入输出维度
        identity = self.downsample(identity)

        # 还原结果
        out += identity
        out = self.relu(out)

        return out


# 构建包含ResidualBlock的网络，CNN
class ResNet_CNN(nn.Module):
    def __init__(self, num_classes=10):
        super(ResNet_CNN, self).__init__()
        # mnist是灰度图，所以输入通道为1，输出通道为16,卷积核为3，步长为1，padding为1说明让输入输出维度不变

        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(16)
        self.relu = nn.ReLU()
        self.res1 = ResidualBlock(16, 16)
        # 这里的stride=2,是因为输入输出维度不一致，需要下采样
        self.res2 = ResidualBlock(16, 32, stride=2)
        self.res3 = ResidualBlock(32, 64, stride=2)
        self.res4 = ResidualBlock(64, 128, stride=2)
        self.res5 = ResidualBlock(128, 128)
        self.res6 = ResidualBlock(128, 256)
        self.res7 = ResidualBlock(256, 256)

        # 用一个自适应均值池化层将每个通道维度变成1*1

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        # 感觉数字特征比较简单，一个全连接层就够了
        self.fc1 = nn.Linear(256, 7)
        self.fc2 = nn.Linear(7, num_classes)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.res1(x)
        x = self.res2(x)
        x = self.res3(x)
        x = self.res4(x)
        x = self.res5(x)
        x = self.res6(x)
        # x = self.res7(x)
        # 64个通道，每个通道1*1，输出64*1*1
        x = self.avg_pool(x)
        # 将数据拉成一维
        x = x.view(x.size(0), -1)
        x = self.fc1(x)
        x = self.fc2(x)
        return x


# 实例化
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = ResNet_CNN().to(device)
# 定义损失函数
loss_f = nn.CrossEntropyLoss()
# 定义优化器
optimizer = optim.Adam(model.parameters(), lr=learning_rate)


# 训练模型
def train(epochs):
    for epoch in range(epochs):
        # 让BN层每一个mini-batch都要更新
        model.train()
        # 总损失
        # train_loss = 0
        # enumerate()函数用于将一个可遍历的数据对象组合为一个索引序列，同时列出数据和数据下标
        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = model(data)
            loss = loss_f(output, target)
            loss.backward()
            optimizer.step()
            # train_loss += loss.item()
            # 每个mini-batch打印一次,loss.item()是一个mini-batch的平均损失
            if batch_idx % log_interval == 0:
                print('Train Epoch:{} [{}/{} ({:.0f}%)]\tLoss:{:.6f}'.format(
                    epoch, batch_idx * len(data), len(train_loader.dataset),
                           100. * batch_idx / len(train_loader), loss.item()
                ))
    # 保存模型 state_dict()是一个字典，保存了网络中所有的参数
    # 转换并保存为torch.jit的模型
    example_input = torch.rand(1, 1, 28, 28).to(device)
    traced_model = torch.jit.trace(model, example_input)
    torch.jit.save(traced_model, "traced_model.pt")



# 测试模型,每一个类别都要统计准确率，并统计总体准确率
#把测试封装成函数
def test():
    correct = 0
    total = 0
    with torch.no_grad():
        for data in test_loader:
            images,labels = data
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data,dim=1)       #从第一维度开始搜索
            total += labels.size(0)
            correct += (predicted==labels).sum().item()

    return correct/total
# main
if __name__ == '__main__':
    epochs = 10
    print("ok")
    train(epochs)
    print(test())
    print("ok")
    # 保存模型 state_dict()是一个字典，保存了网络中所有的参数
    # 转换并保存为torch.jit的模型
    example_input = torch.rand(1, 1, 28, 28).to(device)  # 创建一个形状为 (1, 1, 28, 28) 的随机输入样本，并将其放置在指定的设备上（例如 GPU）
    traced_model = torch.jit.trace(model, example_input)  # 使用 torch.jit.trace 函数对模型进行跟踪（tracing），生成跟踪模型（traced model）
    torch.jit.save(traced_model, "traced_model_15.pt")  # 将跟踪模型保存到 "traced_model.pt" 文件中
"""
import torch
import torchvision
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
#导入依赖模块

epochs = 15
batch_size_train = 16
batch_size_test = 1000
learning_rate = 0.001
log_interval = batch_size_train*2
random_seed = 1
torch.manual_seed(random_seed)
#设定参数

train_loader = torch.utils.data.DataLoader(
torchvision.datasets.MNIST('./data/', train=True, download=True,transform=torchvision.transforms.Compose([torchvision.transforms.ToTensor(),torchvision.transforms.Normalize((0.1307,), (0.3081,))])),batch_size=batch_size_train, shuffle=True)
#加载数据集

class ResidualBlock(torch.nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super(ResidualBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3,stride=stride, padding=1, bias=False)
        self.conv2 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)


        self.relu = nn.ReLU(inplace=True)
    def forward(self,x):
    # 保存输入数据，采用恒等映射
        identity = x
    #
        out =self.conv1(x)

        out = self.bn1(out)

        out = self.relu(out)

        out = out =self.conv2(x)

        out = identity + out

        out = self.relu(out)
    # 返回结果
        return out
#设计Residual模块




class ResNet_CNN(nn.Module):
    def __init__(self,num_classes=10):
        super(ResNet_CNN,self).__init__()
        self.conv1 =nn.Conv2d(1,16,kernel_size=3)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3)
        #self.conv3 = nn.Conv2d(32, 16, kernel_size=3)

        #self.bn1 = nn.BatchNorm2d(16)
        #self.bn2 = nn.BatchNorm2d(32)
        #self.bn3 = nn.BatchNorm2d(16)

        self.relu1 = nn.ReLU()
        self.relu2 = nn.ReLU()
        #self.relu3 = nn.ReLU()

        self.res1 = ResidualBlock(16, 16)
        self.res2 = ResidualBlock(32,32)
        #self.res3 = ResidualBlock(16, 16)

        self.mp = nn.MaxPool2d(2)

        # 用一个自适应均值池化层将每个通道维度变成1*1，此句可选
        self.avg_pool = nn.AdaptiveAvgPool2d((1,1))
        self.fc = nn.Linear(32, num_classes)
    def forward(self,x):
        x = self.conv1(x)
        #x = self.bn1(x)
        x = self.relu1(x)
        x = self.mp(x)
        x = self.res1(x)


        x = self.conv2(x)
        #x = self.bn2(x)
        x = self.relu2(x)
        x = self.mp(x)
        x = self.res2(x)

        #x = self.conv3(x)
        #x = self.bn3(x)
        #x = self.relu3(x)
        #x = self.mp(x)
        #x = self.res3(x)

        # n个通道，每个通道1*1，输出n*1*1
        x = self.avg_pool(x)
        # 将数据拉成一维
        x = x.view(x.size(0),-1)
        x = self.fc(x)
        return x

#定义完整的卷积神经网络(ResNet_CNN)


device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


model = ResNet_CNN().to(device)
#实例化网络模型


loss_f = nn.CrossEntropyLoss()
#定义损失函数


optimizer = optim.Adam(model.parameters(),lr=learning_rate)
#定义优化器


def train(epochs):
    for epoch in range(epochs):
        model.train()
        for batch_idx,(data,target) in enumerate(train_loader):
            data,target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = model(data)
            loss = loss_f(output,target)
            loss.backward()
            optimizer.step()
            if batch_idx % log_interval == 0:
                print('Train Epoch:{} [{}/{} ({:.0f}%)]\tLoss:{:.6f}'.format(epoch,batch_idx*len(data),len(train_loader.dataset),100.*batch_idx/len(train_loader),loss.item()))
#训练函数

test_loader = torch.utils.data.DataLoader(
    torchvision.datasets.MNIST('./data/', train=False, download=True,transform=torchvision.transforms.Compose([torchvision.transforms.ToTensor(),torchvision.transforms.Normalize((0.1307,), (0.3081,))])),
    batch_size=batch_size_test, shuffle=True)
#测试函数

def test():
    correct = 0
    total = 0
    with torch.no_grad():
        for data in test_loader:
            images,labels = data
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data,dim=1)       #从第一维度开始搜索
            total += labels.size(0)
            correct += (predicted==labels).sum().item()

    return correct/total

if __name__ == '__main__':
    epochs=11
    train(epochs)
    print(test())
    #print(test(model,test_loader))
#执行函数


example_input = torch.rand(2, 1, 28, 28).to(device)
traced_model = torch.jit.trace(model, example_input)
torch.jit.save(traced_model, "traced_model1.pt")